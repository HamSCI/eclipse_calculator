import pandas as pd

# Geographiclib - https://geographiclib.sourceforge.io/Python/2.0/
# conda install conda-forge::geographiclib
from geographiclib.geodesic import Geodesic
geod = Geodesic.WGS84

class RayTracePaths(object):
    def __init__(self,path_dcts):
        """
        Class for processing ray trace path transmitter, receiver, and end point locations.

        path_dcts: List of dictionaries specifying paths. Example:
            pdcts = []
            pdct = {}
            pdct['tx_lat']  =  30.
            pdct['tx_lon']  = -87.
            pdct['tx_lbl']  = 'TX 1'
            pdct['end_lat'] =  50.
            pdct['end_lon'] = -95.
            pdct['end_lbl'] = 'Path 1'
            pdcts.append(pdct)
        """
        self.df = pd.DataFrame(path_dcts)
        self.__add_endPoints__()
        self.__compute_rangeAzms__()
        
    def __compute_rangeAzms__(self):
        """
        Use geographic lib to calcuate the ranges [km] and azimuths [deg clockwise from North]
        of paths dataframe.
        """
        paths_df = self.df
        
        new_rows = []
        for rinx,row in paths_df.iterrows():
            tx_lat = row['tx_lat']
            tx_lon = row['tx_lon']
            endPts = ['rx','end']
            for endPt in endPts:
                end_lat = row.get(endPt+'_lat')
                end_lon = row.get(endPt+'_lon')
                if end_lat is not None:
                    # Determine the ranges and azimuth along the profile path.
                    invl    = geod.InverseLine(tx_lat,tx_lon,end_lat,end_lon)
                    dist    = invl.s13*1e-3   # Distance in km
                    azm     = invl.azi1
    
                    row['tx_{!s}_range_km'.format(endPt)] = dist
                    row['tx_{!s}_azm'.format(endPt)]      = azm
            new_rows.append(row)
    
        new_paths_df = pd.DataFrame(new_rows)
        self.df = new_paths_df

    def __add_endPoints__(self):
        """
        For each row in self.df, if a 'tx_end_range_km' is defined but 'end_lat' is not,
        compute and add an 'end_lat' and 'end_lon' from the tranmitter location
        in the direction of the receiver location for the distance 'tx_end_range_km'.
        """
        paths_df = self.df
        
        new_rows = []
        for rinx,row in paths_df.iterrows():
            if ('tx_end_range_km' in row.keys()) and ('rx_lat' in row.keys()) and ('end_lat' not in row.keys()):
                tx_lat = row['tx_lat']
                tx_lon = row['tx_lon']
                rx_lat = row['rx_lat']
                rx_lon = row['rx_lon']
                
                invl    = geod.InverseLine(tx_lat,tx_lon,rx_lat,rx_lon)
                rx_azm  = invl.azi1
                rng_m  = row['tx_end_range_km']*1e3

                tmp    = geod.Direct(tx_lat, tx_lon, rx_azm, rng_m)
                row['end_lat'] = tmp['lat2']
                row['end_lon'] = tmp['lon2']

                if (row.get('end_lbl') is None) and (row.get('rx_lbl') is not None):
                    row['end_lbl'] = row['rx_lbl']
                    
            new_rows.append(row)
        new_paths_df = pd.DataFrame(new_rows)
        
        self.df = new_paths_df

    def generate_run_list(self,dates_UTC,freqs_MHz,event=''):
        """
        Generate a dataframe with the information needed to run raytraces for 
        each of the paths in self.df.

        dates_UTC: list of datetimes to run the raytrace
        freq_MHz:  list of frequencies in MHz
        event: string with the event name
        """
        new_rows = []
        for date_UTC in dates_UTC:
            for freq_MHz in freqs_MHz:
                for rinx,row in self.df.iterrows():
                    tx_lbl = row.get('tx_lbl')
                    if tx_lbl is None:
                        pass
                    elif tx_lbl.upper() == 'WWV':
                        if freq_MHz not in [2.5, 5, 10, 15, 20, 25]:
                            continue
                    elif tx_lbl.upper() == 'WWVH':
                        if freq_MHz not in [2.5, 5, 10, 15]:
                            continue
                    elif tx_lbl.upper() == 'CHU':
                        if freq_MHz not in [3.33, 7.85, 14.67]:
                            continue
                    
                    row['date_UTC'] = date_UTC
                    row['freq_MHz'] = freq_MHz
                    row['event']    = event

                    new_rows.append(row)
        new_df = pd.DataFrame(new_rows)

        return new_df