# -*- coding: utf-8 -*-
##
##  generate_return_periods.py
##  spt_lsm_autorapid_process
##
##  Created by Alan D. Snow and Scott D. Christensen.
##  Copyright © 2015-2016 Alan D Snow and Scott D. Christensen. All rights reserved.
##  License: BSD-3 Clause

import multiprocessing
import netCDF4 as nc
import numpy as np
from HydroStats.VDF import VDF

#local
from ..dataset import RAPIDDataset
from utilities import partition

def generate_single_return_period(qout_file, return_period_file, 
                                  rivid_index_list, storm_duration_days, mp_lock):
    """
    This function calculates a single return period for a single reach
    """
    with RAPIDDataset(qout_file) as qout_nc_file:
        time_array = qout_nc_file.get_time_array(return_datetime=True)
        for rivid_index in rivid_index_list:
            streamflow = np.nan_to_num(qout_nc_file.get_qout_index(rivid_index))
            max_flow = np.amax(streamflow)
            if max_flow > 0.01:
                vdf_calc = VDF(time_array, 
                               streamflow,
                               np.array([storm_duration_days*24*60]),
                               ['kde', 'silverman'],
                               True,
                               1e-4,
                               )
                               
        ##                vdf_calc = VDF(time_array, 
        ##                               streamflow,
        ##                               np.array([storm_duration_days*24*60]),
        ##                               ['gev'],
        ##                               True
        ##                               )
                mp_lock.acquire()
                return_period_nc = nc.Dataset(return_period_file, 'a')
                return_period_nc.variables['max_flow'][rivid_index] = max_flow
                return_period_nc.variables['return_period_100'][rivid_index] = vdf_calc.calculate_return_period_curve(100)[0]
                return_period_nc.variables['return_period_50'][rivid_index] = vdf_calc.calculate_return_period_curve(50)[0]
                return_period_nc.variables['return_period_20'][rivid_index] = vdf_calc.calculate_return_period_curve(20)[0]
                return_period_nc.variables['return_period_10'][rivid_index] = vdf_calc.calculate_return_period_curve(10)[0]
                return_period_nc.variables['return_period_2'][rivid_index] = vdf_calc.calculate_return_period_curve(2)[0]
                print return_period_nc.variables['return_period_100'][rivid_index], return_period_nc.variables['return_period_10'][rivid_index]
                return_period_nc.close()
                mp_lock.release()
            else:
                mp_lock.acquire()
                return_period_nc = nc.Dataset(return_period_file, 'a')
                return_period_nc.variables['max_flow'][rivid_index] = max_flow
                return_period_nc.variables['return_period_100'][rivid_index] = max_flow
                return_period_nc.variables['return_period_50'][rivid_index] = max_flow
                return_period_nc.variables['return_period_20'][rivid_index] = max_flow
                return_period_nc.variables['return_period_10'][rivid_index] = max_flow
                return_period_nc.variables['return_period_2'][rivid_index] = max_flow
                return_period_nc.close()
                mp_lock.release()
                
def generate_single_return_period_mp_worker(args):
    """
    Multiprocess worker function for generate_single_return_period
    """
    generate_single_return_period(qout_file=args[0], 
                                  return_period_file=args[1], 
                                  rivid_index_list=args[2], 
                                  storm_duration_days=args[3], 
                                  mp_lock=args[4])
    
def generate_return_periods(qout_file, return_period_file, num_cpus, storm_duration_days=7):
    """
    Generate return period from RAPID Qout file
    """

    #get ERA Interim Data Analyzed
    with RAPIDDataset(qout_file) as qout_nc_file:
        print "Setting up Return Periods File ..."
        return_period_nc = nc.Dataset(return_period_file, 'w')
        
        return_period_nc.createDimension('rivid', qout_nc_file.size_river_id)

        timeSeries_var = return_period_nc.createVariable('rivid', 'i4', ('rivid',))
        timeSeries_var.long_name = (
            'Unique NHDPlus COMID identifier for each river reach feature')

        max_flow_var = return_period_nc.createVariable('max_flow', 'f8', ('rivid',))
        return_period_100_var = return_period_nc.createVariable('return_period_100', 'f8', ('rivid',))
        return_period_50_var = return_period_nc.createVariable('return_period_50', 'f8', ('rivid',))
        return_period_20_var = return_period_nc.createVariable('return_period_20', 'f8', ('rivid',))
        return_period_10_var = return_period_nc.createVariable('return_period_10', 'f8', ('rivid',))
        return_period_2_var = return_period_nc.createVariable('return_period_2', 'f8', ('rivid',))

        lat_var = return_period_nc.createVariable('lat', 'f8', ('rivid',),
                                                  fill_value=-9999.0)
        lat_var.long_name = 'latitude'
        lat_var.standard_name = 'latitude'
        lat_var.units = 'degrees_north'
        lat_var.axis = 'Y'

        lon_var = return_period_nc.createVariable('lon', 'f8', ('rivid',),
                                                  fill_value=-9999.0)
        lon_var.long_name = 'longitude'
        lon_var.standard_name = 'longitude'
        lon_var.units = 'degrees_east'
        lon_var.axis = 'X'

        return_period_nc.variables['lat'][:] = qout_nc_file.qout_nc.variables['lat'][:]
        return_period_nc.variables['lon'][:] = qout_nc_file.qout_nc.variables['lon'][:]

        river_id_list = qout_nc_file.get_river_id_array()
        return_period_nc.variables['rivid'][:] = river_id_list
        return_period_nc.close()
        
    print "Extracting Data and Generating Return Periods ..."
    mp_lock = multiprocessing.Manager().Lock()
    job_combinations = []
    partition_list, partition_index_list = partition(river_id_list, num_cpus*2)
    for sub_partition_index_list in partition_index_list:
        job_combinations.append((qout_file,
                                 return_period_file,
                                 sub_partition_index_list, 
                                 storm_duration_days, 
                                 mp_lock
                                 ))

    pool = multiprocessing.Pool(num_cpus)
    pool.map(generate_single_return_period_mp_worker,
             job_combinations)
    pool.close()
    pool.join()