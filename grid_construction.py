import random
import numpy as np
#import parameters as par
import config as cfg
from datetime import datetime
from astropy.table import Table
from astropy.io import ascii
import hyperion_octree_stats as hos
from gridstats import gridstats
from octree_zoom import octree_zoom_bbox_filter
from plot_generate import proj_plots
from yt.mods import *
from yt.geometry.oct_container import OctreeContainer
from yt.geometry.selection_routines import AlwaysSelector

import constants as const

random.seed('octree-demo')
 
import pdb,ipdb
import os.path
import sys



def yt_octree_generate():
    
   
    

    fname = cfg.model.hydro_dir+cfg.model.Gadget_snap_name

    print '[grid_construction]: bbox_lim = ',cfg.par.bbox_lim

    
    bbox = [[-2.*cfg.par.bbox_lim,2.*cfg.par.bbox_lim],
            [-2.*cfg.par.bbox_lim,2.*cfg.par.bbox_lim],
            [-2.*cfg.par.bbox_lim,2.*cfg.par.bbox_lim]]
 
             
    

    unit_base = {'UnitLength_in_cm'         : cfg.par.unit_length*1.e3*const.pc,
                 'UnitMass_in_g'            : cfg.par.unit_mass*const.msun,
                 'UnitVelocity_in_cm_per_s' : cfg.par.unit_velocity}

    print '[grid_construction]: unit_base = ',unit_base

    
    def _metaldens(field,data):
        return (data["PartType0","Density"]*data["PartType0","Metallicity"])
        
    add_field("metaldens",function=_metaldens,units="g/cm**3")

    
    if cfg.par.zoom == False:
    
        pf = load(fname,unit_base=unit_base,bounding_box=bbox,over_refine_factor=cfg.par.oref,n_ref=cfg.par.n_ref)

    
    else:
    
        pf = octree_zoom_bbox_filter(fname,unit_base,bbox)


    pf.index


    
  



   
    #---------------------------------------------------------------
    #PLOTTING DIAGNOSTIC PROJECTION PLOTS
    #---------------------------------------------------------------
    
    #proj_plots(pf)
    





    from yt.data_objects.particle_unions import ParticleUnion
    pu = ParticleUnion("all", list(pf.particle_types_raw))
    
    saved = pf.index.oct_handler.save_octree()
 
    always = AlwaysSelector(None)
    ir1 = pf.index.oct_handler.ires(always)  #refinement levels
    fc1 = pf.index.oct_handler.fcoords(always)  #coordinates in kpc
    fw1 = pf.index.oct_handler.fwidth(always)  #width of cell in kpc
    

    

    print '----------------------------'
    print 'yt Octree Construction Stats'
    print '----------------------------'
    print ' n_ref = ',pf.index.oct_handler.n_ref
    print ' max_level = ',pf.index.oct_handler.max_level
    print ' nocts = ',pf.index.oct_handler.nocts
    print '----------------------------'
        
    gridstats(ir1,fc1,fw1)
    
    



    #==================================



    refined = saved['octree']
    refined2 = []

 
    for i in range(len(refined)):
        if refined[i] == 1: refined2.append(True)
        if refined[i] == 0: refined2.append(False)

    refined = refined2



    #smooth the data on to the octree
    
    volume = np.zeros(len(refined))
    wTrue = np.where(np.array(refined) == True)[0]
    wFalse = np.where(np.array(refined) == False)[0]
    volume[wFalse] = (fw1 * const.pc * 1.e3)**3.
    

   

    if cfg.par.CONSTANT_DUST_GRID == False: 

 
        '''USING YT SMOOTHING'''

        
        from particle_smooth_yt import yt_smooth
        metallicity_smoothed,density_smoothed,masses_smoothed = yt_smooth(pf)

        
        '''
        #DEBUG 061314
        wm = np.where(metallicity_smoothed > 0)[0]
        print np.median(metallicity_smoothed[wm])
        wm2 = np.where(metallicity_smoothed > (np.min(metallicity_smoothed[wm]*2.)))
        print np.median(metallicity_smoothed[wm2])
        wmless = np.where(metallicity_smoothed < np.min(metallicity_smoothed[wm2]))[0]
        metallicity_smoothed[wmless] = np.median(metallicity_smoothed[wm2])
        print np.median(metallicity_smoothed)


        wd = np.where(density_smoothed > 0)[0]
        print np.median(density_smoothed[wd])
        wd2 = np.where(density_smoothed > (np.min(density_smoothed[wd]*200.)))
        print np.median(density_smoothed[wd2])
        wdless = np.where(density_smoothed < np.min(density_smoothed[wd2]))[0]
        density_smoothed[wdless] = np.median(density_smoothed[wd2])
        print np.median(density_smoothed)

        '''





        dust_smoothed = np.zeros(len(refined))
        
        print '[grid_construction: ] len(wFalse) = ',len(wFalse)
        print '[grid_construction: ] len(metallicity_smoothed) = ',len(metallicity_smoothed)

       
        #some of the outer grids in the octree can have zeros for
        #metallicity_smoothed and density_smoothed; since this causes
        #nans and infs down the road, we just set these to the minimum
        #nonzero value
        
        
        #dust_smoothed[wFalse] = 1.e10*const.msun*masses_smoothed * metallicity_smoothed * cfg.par.dusttometals_ratio / volume[wFalse]
        #dust_smoothed[wTrue] = 0
              
        dust_smoothed[wFalse] = metallicity_smoothed * density_smoothed * cfg.par.dusttometals_ratio 

        
    else:
        print 'cfg.par.CONSTANT_DUST_GRID=True'
        print 'setting constant dust grid to 4.e-22'
        dust_smoothed = np.zeros(len(refined))+4.e-23




    
    





     #file I/O
    print 'Writing Out the Coordinates and Logical Tables'
   

    xmin = fc1[:,0]-fw1[:,0]/2.
    xmax = fc1[:,0]+fw1[:,0]/2.
    ymin = fc1[:,1]-fw1[:,1]/2.
    ymax = fc1[:,1]+fw1[:,1]/2.
    zmin = fc1[:,2]-fw1[:,2]/2.
    zmax = fc1[:,2]+fw1[:,2]/2.


   
    xcent_orig,ycent_orig,zcent_orig,dx,dy,dz = grid_center(xmin,xmax,ymin,ymax,zmin,zmax)
    boost = np.array([xcent_orig,ycent_orig,zcent_orig])*1.e3*const.pc

    '''
    xmin,xmax,ymin,ymax,zmin,zmax = grid_coordinate_boost(xmin,xmax,ymin,ymax,zmin,zmax)
   

    coordinates_Table = Table([fc1[:,0]-fw1[:,0]/2.,fc1[:,0]+fw1[:,0]/2.,fc1[:,1]-fw1[:,1]/2.,
                               fc1[:,1]+fw1[:,1]/2.,fc1[:,2]-fw1[:,2]/2.,fc1[:,2]+fw1[:,2]/2.],
                              names = ['xmin','xmax','ymin','ymax','zmin','zmax'])
    
    ascii.write(coordinates_Table,cfg.par.PD_output_dir+cfg.par.Auto_positions_file)

    '''

    logical_Table = Table([refined[:]],names=['logical'])
    ascii.write(logical_Table,cfg.model.PD_output_dir+cfg.model.Auto_TF_file)


    dust_dens_Table = Table([dust_smoothed[:]],names=['dust density'])
    ascii.write(dust_dens_Table,cfg.model.PD_output_dir+cfg.model.Auto_dustdens_file)
        


    #return refined,dust_smoothed,xmin,xmax,ymin,ymax,zmin,zmax,boost
    return refined,dust_smoothed,fc1,fw1,boost


def grid_coordinate_boost(xmin,xmax,ymin,ymax,zmin,zmax):
    
    print '\n boosting coordinates to [0,0,0] centering \n'
    xcent,ycent,zcent,dx,dy,dz = grid_center(xmin,xmax,ymin,ymax,zmin,zmax)
    xmin -= xcent
    xmax -= xcent
    ymin -= ycent
    ymax -= ycent
    zmin -= zcent
    zmax -= zcent
                
    return xmin,xmax,ymin,ymax,zmin,zmax


def stars_coordinate_boost(star_list,boost):
    
#center the stars
    nstars = len(star_list)
    for i in range(nstars):
        star_list[i].positions[0] -= boost[0]
        star_list[i].positions[1] -= boost[1]
        star_list[i].positions[2] -= boost[2]
        
    return star_list



def grid_center(xmin,xmax,ymin,ymax,zmin,zmax):
    
    xcent = np.mean([min(xmin),max(xmax)])
    ycent = np.mean([min(ymin),max(ymax)])
    zcent = np.mean([min(zmin),max(zmax)])
    
    
    #dx,dy,dz are the edges of the parent grid
    dx = (max(xmax)-min(xmin))/2
    dy = (max(ymax)-min(ymin))/2.
    dz = (max(zmax)-min(zmin))/2.

    '''
    
    dx = np.absolute(xcent - min(xmin))
    dy = np.absolute(ycent - min(ymin))
    dz = np.absolute(zcent - min(zmin))
    '''

    return xcent,ycent,zcent,dx,dy,dz




