import os
import datetime

import numpy as np
import pandas as pd

import matplotlib as mpl
from matplotlib.collections import PolyCollection
from matplotlib.patches import Polygon
from matplotlib import pyplot as plt

import cartopy
import cartopy.crs as ccrs
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

# Geographiclib - https://geographiclib.sourceforge.io/Python/2.0/
# conda install conda-forge::geographiclib
from geographiclib.geodesic import Geodesic
geod = Geodesic.WGS84

from . import calcSun
from . import eclipse_calc

class EclipseData(object):
    def __init__(self,fname,meta={},track_kwargs={}):
        """
        Load a CSV containing eclipse obscuration data.
        """
        df = pd.read_csv(fname,comment='#')

        height = df['height'].unique()
        n_heights = len(height)
        assert n_heights  == 1, f'One height expected, got: {n_heights}'
        height = height[0]

        # Calculate vectors of center lats and lons.
        center_lats = np.sort(df['lat'].unique())
        center_lons = np.sort(df['lon'].unique())

        # Find the lat/lon step size.
        dlat = center_lats[1] - center_lats[0]
        dlon = center_lons[1] - center_lons[0]

        # Calculate vectors of boundary lats and lons.
        lat_0   = center_lats.min() - dlat/2.
        lat_1   = center_lats.max() + dlat/2.
        lats    = np.arange(lat_0,lat_1+dlat,dlat)

        lon_0 = center_lons.min() - dlon/2.
        lon_1 = center_lons.max() + dlon/2.
        lons    = np.arange(lon_0,lon_1+dlon,dlon)
        
        # These if statements are to handle an error that can occur
        # when dlat or dlon are very small and you get the wrong number
        # of elements due to a small numerical error.
        if len(lats) > len(center_lats)+1:
            lats=lats[:len(center_lats)+1]

        if len(lons) > len(center_lons)+1:
            lons=lons[:len(center_lons)+1]


        cshape      = (len(center_lats),len(center_lons))

        meta['fname']    = fname        
        self.meta        = meta
        self.df          = df
        self.center_lats = center_lats
        self.center_lons = center_lons
        self.cshape      = cshape
        self.lats        = lats
        self.lons        = lons
        self.dlat        = dlat
        self.dlon        = dlon
        self.height      = height
    
        # Load track data.
        self.track_kwargs = track_kwargs
        df_track_csv = fname.replace('MAX_OBSCURATION','ECLIPSE_TRACK')
        if os.path.exists(df_track_csv):
            df_track = pd.read_csv(df_track_csv,parse_dates=[0],comment='#')
            df_track = df_track.set_index('date_ut')
            
            self.df_track = df_track
        else:
            print('File not found: {!s}'.format(df_track_csv))
            print('No eclipse track data loaded.')
            self.df_track = None
        
    def get_obsc_arr(self,obsc_min=0,obsc_max=1):
        """
        Convert the Obscuration DataFrame to a 2D numpy array that can easily be plotted with pcolormesh.

        obsc_min: obscuration values less than this number will be converted to np.nan
        obsc_max: obscuration values greater than this number will be converted to np.nan
        """
        df = self.df.copy()
        
        if obsc_min > 0:
            tf = df['obsc'] < obsc_min
            df.loc[tf,'obsc'] = np.nan
            
        if obsc_max < 1:
            tf = df['obsc'] > obsc_max
            df.loc[tf,'obsc'] = np.nan
            
        obsc_arr    = df['obsc'].to_numpy().reshape(self.cshape)
        
        return obsc_arr
    
    def overlay_obscuration(self,ax,obsc_min=0,alpha=0.65,cmap='gray_r',vmin=0,vmax=1,zorder=1):
        """
        Overlay obscuration values on a map.
        
        ax: axis object to overlay obscuration on.
        """
        obsc_min = self.meta.get('obsc_min',obsc_min)
        alpha    = self.meta.get('alpha',alpha)
        cmap     = self.meta.get('cmap',cmap)
        vmin     = self.meta.get('vmin',vmin)
        vmax     = self.meta.get('vmax',vmax)
        
        lats     = self.lats
        lons     = self.lons
        obsc_arr = self.get_obsc_arr(obsc_min=obsc_min)
        pcoll    = ax.pcolormesh(lons,lats,obsc_arr,vmin=vmin,vmax=vmax,cmap=cmap,zorder=zorder,alpha=alpha)
        
        return {'pcoll':pcoll}
    
    def overlay_track(self,ax,annotate=False,xlim=None,ylim=None,**kw_args):
        """
        Overlay eclipse track on map.
        
        ax: axis object to overlay track values on.
        """
        if self.df_track is None:
            print('No eclipse track data loaded.')
            return
        else:
            df_track = self.df_track
        
        # Annotate places specifed in meta['track_annotate'], but make sure
        # the places are actually on the track.

        # Set default annotation style dictionary.
        tp = {}
        tp['bbox']          = dict(boxstyle='round', facecolor='white', alpha=0.75)
        tp['fontweight']    = 'bold'
        tp['fontsize']      = 12
        tp['zorder']        = 975
        tp['va']            = 'top'

        tas_new = []
        tas = self.meta.get('track_annotate',[]).copy()
        for ta in tas:
            ta_se   = ta.get('startEnd','start')

            tr_lats = df_track['lat'].to_numpy()
            tr_lons = df_track['lon'].to_numpy()

            ta_lat = ta['lat']
            ta_lon = ta['lon']

            ta_lats = np.ones_like(tr_lats)*ta_lat
            ta_lons = np.ones_like(tr_lons)*ta_lon

            ta_rngs = []
            for ta_lat,ta_lon,tr_lat,tr_lon in zip(ta_lats,ta_lons,tr_lats,tr_lons):
                # Determine the ranges and azimuth along the profile path.
                invl    = geod.InverseLine(ta_lat,ta_lon,tr_lat,tr_lon)
                dist    = invl.s13*1e-3   # Distance in km
                # azm     = invl.azi1
                ta_rngs.append(dist)
            
            ta_inx  = np.argmin(ta_rngs)
            
            ta['lat']   = tr_lats[ta_inx]
            ta['lon']   = tr_lons[ta_inx]

            if ta_se == 'start':
                ta['text']  = df_track.index[ta_inx].strftime('%d %b %Y\n%H%M UT')
            else:
                ta['text']  = df_track.index[ta_inx].strftime('%H%M UT')
            
            tp_tmp  = tp.copy()
            ta_tp   = ta.get('tp',{})
            tp_tmp.update(ta_tp)
            ta['tp']    = tp_tmp

            tas_new.append(ta)
        tas = tas_new

        ta_lats = []
        ta_lons = []
        for ta in tas:
            ta_lat  = ta['lat']
            ta_lon  = ta['lon']
            ta_text = ta['text']
            ta_tp   = ta['tp']
            ax.text(ta_lon,ta_lat,'{!s}'.format(ta_text),**ta_tp)

            ta_lats.append(ta_lat)
            ta_lons.append(ta_lon)

        for inx,(rinx,row_0) in enumerate(df_track.iterrows()):
            lat_0 = row_0['lat']
            lon_0 = row_0['lon']

            if len(ta_lats) > 0:
                if lat_0 < np.min(ta_lats) or lat_0 > np.max(ta_lats): continue

            if len(ta_lons) > 0:
                if lon_0 < np.min(ta_lons) or lon_0 > np.max(ta_lons): continue

            if annotate:
                if inx == 0:
                    ax.text(lon_0,lat_0,'{!s}'.format(rinx.strftime('%H%M UT')),**tp)
                if inx == len(df_track)-1:
                    ax.text(lon_0,lat_0,'{!s}'.format(rinx.strftime('%H%M UT')),**tp)

            if inx == len(df_track)-1:
                continue

            row_1 = df_track.iloc[inx+1]
            lat_1 = row_1['lat']
            lon_1 = row_1['lon']

            box = mpl.transforms.TransformedBbox(mpl.transforms.Bbox([[0,0],[1,1]]), ax.transAxes)
            ax.annotate('', xy=(lon_1,lat_1), xytext=(lon_0,lat_0),zorder=950,
                    xycoords='data', size=20,
                    arrowprops=dict(facecolor='red', ec = 'none', arrowstyle="simple",
                connectionstyle="arc3,rad=-0.1"),clip_box=box,clip_on=True)        

        return {}

class solarTimeseries(object):
    def __init__(self,sTime=None,eTime=None,lat=None,lon=None,dt_minutes=1):
        """
        Class for overlaying solar elevation angle and eclipse obscuration on timeseries axis objects.
        sTime:      Datetime to start solar calculations.
        eTime:      Datetime to end solar calculations.
        lat:        Latitude of observer.
        lon:        Longitude of observer.
        dt_minutes: Time resolution in minutes of solar calculations.
        """

        self.sTime      = sTime
        self.eTime      = eTime
        self.lat        = lat
        self.lon        = lon
        self.dt_minutes = dt_minutes
        self.data       = {}

        if not self.__check_parameters__():
            print('WARNING: Incomplete inputs to solarTimeseries(); will not perform calculations')

    def __check_parameters__(self):
        """
        Returns False if any of the sTime, eTime, lat, or lon are None.
        """
        if self.sTime is None or self.eTime is None \
                or self.lat is None or self.lon is None:
            return False
        else:
            return True

    def __calcSolarAzEls__(self):
        """
        Compute solar azimuths and elevations using parameters defined when object was created.

        Results are stored in a dataframe in self.data['solarAzEls']
        """
        sTime       = self.sTime
        eTime       = self.eTime
        lat         = self.lat
        lon         = self.lon
        dt_minutes  = self.dt_minutes

        dt          = datetime.timedelta(minutes=dt_minutes)
        times = [sTime]
        while times[-1] < eTime:
                times.append(times[-1]+dt)

        azs,els     = calcSun.calculate_solarAzEl(times,lat,lon)
        solarAzEls  = pd.DataFrame({'el':els,'az':azs},index=times)

        self.data['solarAzEls'] = solarAzEls

    def __calcSolarEclipse__(self):
        """
        Compute solar eclipse obscurations using parameters defined when object was created.

        Results are stored in a dataframe in self.data['solarEclipse']
        """
        sTime       = self.sTime
        eTime       = self.eTime
        lat         = self.lat
        lon         = self.lon
        dt_minutes  = self.dt_minutes

        solar_dt    = datetime.timedelta(minutes=dt_minutes)
        solar_times = [sTime]
        while solar_times[-1] < eTime:
            solar_times.append(solar_times[-1]+solar_dt)
        obsc        = eclipse_calc.calculate_obscuration(solar_times,lat,lon)
        df = pd.DataFrame({'obsc':obsc}, index = solar_times)
        self.data['solarEclipse'] = df

    def overlaySolarElevation(self,ax,ylim=(0,90),
            ylabel='Solar Elevation Angle',
            grid=False,color='0.6',ls='-.',lw=4,**kwargs):
        """
        Overplot the solar elevation on a timeseries axis object. The new data
        will be plotted on a twin axis created by ax.twinx()

        ax: Axis object of original timeseries. X-axis should use UTC datetimes.
        """
        if not self.__check_parameters__():
            print('WARNING: Incomplete inputs to solarTimeseries().')
            print('         Cannot overlay solar elevations angles.')
            return

        if 'solarAzEls' not in self.data:
            self.__calcSolarAzEls__()

        azEls   = self.data['solarAzEls']
        sza_xx  = azEls.index
        sza_yy  = azEls['el']

        ax_sza = ax.twinx()
        ax_sza.plot(sza_xx,sza_yy,color=color,ls=ls,lw=lw,**kwargs)
        ax_sza.set_ylabel(ylabel)
        ax_sza.set_ylim(ylim)
        ax_sza.grid(grid)

    def overlayEclipse(self,ax,ylim=(1.,0.),
            ylabel='Eclipse Obscuration',
            color='b',alpha=0.5,ls=':',lw=4,grid=False,
            spine_position=1.06,**kwargs):
        """
        Overplot the eclipse obscuration on a timeseries axis object. The new data
        will be plotted on a twin axis created by ax.twinx()

        ax: Axis object of original timeseries. X-axis should use UTC datetimes.
        spine_position: Position of spine in transAxes coordinates so. Default set to
            1.10 so that this spine does not overlap with Solar Elevation Angle.
        """
        if not self.__check_parameters__():
            print('WARNING: Incomplete inputs to solarTimeseries().')
            print('         Cannot overlay solar eclipse obscurations.')
            return

        if 'solarEclipse' not in self.data:
            self.__calcSolarEclipse__()

        solar_times = self.data['solarEclipse'].index
        obsc        = self.data['solarEclipse']['obsc']

        ax_ecl = ax.twinx()
        ax_ecl.plot(solar_times,obsc,color=color,alpha=alpha,ls=ls,lw=lw,**kwargs)
        ax_ecl.set_ylabel(ylabel)
        ax_ecl.set_ylim(ylim)
        ax_ecl.grid(grid)
        if spine_position is not None:
            ax_ecl.spines.right.set_position(("axes", spine_position))
