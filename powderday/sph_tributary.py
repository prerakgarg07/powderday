from __future__ import print_function
import numpy as np
import yt

from hyperion.model import Model
import matplotlib as mpl
mpl.use('Agg')
import powderday.config as cfg

from powderday.grid_construction import yt_octree_generate
from powderday.find_order import find_order
import powderday.powderday_test_octree as pto
import powderday.hyperion_octree_stats as hos

from hyperion.dust import SphericalDust

from powderday.helpers import energy_density_absorbed_by_CMB
from powderday.analytics import dump_cell_info

def find_nearest(array,value):
    idx = (np.abs(np.array(array)-value)).argmin()
    return idx


#only comes to be necessary if cfg.par.otf_extinction is set
def _dust_density(field,data):
    return data.ds.arr(data[('PartType3','Dust_Density')],'code_mass/code_length**3')

def _size_with_units(field,data):
    return data.ds.parameters['size']

def sph_m_gen(fname,field_add):
    
    refined,dustdens,fc1,fw1,reg,ds = yt_octree_generate(fname,field_add)
    
    if yt.__version__ == '4.0.dev0':
        xmin = (fc1[:,0]-fw1[:,0]/2.).to('cm') #in proper cm 
        xmax = (fc1[:,0]+fw1[:,0]/2.).to('cm')
        ymin = (fc1[:,1]-fw1[:,1]/2.).to('cm')
        ymax = (fc1[:,1]+fw1[:,1]/2.).to('cm')
        zmin = (fc1[:,2]-fw1[:,2]/2.).to('cm')
        zmax = (fc1[:,2]+fw1[:,2]/2.).to('cm')
    else:
        xmin = (fc1[:,0]-fw1[:,0]/2.).convert_to_units('cm') #in proper cm
        xmax = (fc1[:,0]+fw1[:,0]/2.).convert_to_units('cm')
        ymin = (fc1[:,1]-fw1[:,1]/2.).convert_to_units('cm')
        ymax = (fc1[:,1]+fw1[:,1]/2.).convert_to_units('cm')
        zmin = (fc1[:,2]-fw1[:,2]/2.).convert_to_units('cm')
        zmax = (fc1[:,2]+fw1[:,2]/2.).convert_to_units('cm')

    #dx,dy,dz are the edges of the parent grid
    dx = (np.max(xmax)-np.min(xmin)).value
    dy = (np.max(ymax)-np.min(ymin)).value
    dz = (np.max(zmax)-np.min(zmin)).value


    xcent = float(ds.quan(cfg.model.x_cent,"code_length").to('cm').value)
    ycent = float(ds.quan(cfg.model.y_cent,"code_length").to('cm').value)
    zcent = float(ds.quan(cfg.model.z_cent,"code_length").to('cm').value)

    boost = np.array([xcent,ycent,zcent])
    print ('[sph_tributary] boost = ',boost)
    print ('[sph_tributary] xmin (pc)= ',np.min(xmin.to('pc')))
    print ('[sph_tributary] xmax (pc)= ',np.max(xmax.to('pc')))
    print ('[sph_tributary] ymin (pc)= ',np.min(ymin.to('pc')))
    print ('[sph_tributary] ymax (pc)= ',np.max(ymax.to('pc')))
    print ('[sph_tributary] zmin (pc)= ',np.min(zmin.to('pc')))
    print ('[sph_tributary] zmax (pc)= ',np.max(zmax.to('pc')))
    #Tom Robitaille's conversion from z-first ordering (yt's default) to
    #x-first ordering (the script should work both ways)



    refined_array = np.array(refined)
    refined_array = np.squeeze(refined_array)
    
    order = find_order(refined_array)
    refined_reordered = []
    dustdens_reordered = np.zeros(len(order))
    


    
    for i in range(len(order)): 
        refined_reordered.append(refined[order[i]])
        dustdens_reordered[i] = dustdens[order[i]]


    refined = refined_reordered
    dustdens=dustdens_reordered

    #hyperion octree stats
    max_level = hos.hyperion_octree_stats(refined)


    pto.test_octree(refined,max_level)

    dump_cell_info(refined,fc1,fw1,xmin,xmax,ymin,ymax,zmin,zmax)
    np.save('refined.npy',refined)
    np.save('density.npy',dustdens)
    

    #========================================================================
    #Initialize Hyperion Model
    #========================================================================

    m = Model()
    


    print ('Setting Octree Grid with Parameters: ')



    #m.set_octree_grid(xcent,ycent,zcent,
    #                  dx,dy,dz,refined)
    m.set_octree_grid(0,0,0,dx/2,dy/2,dz/2,refined)    

    #get CMB:
    
    energy_density_absorbed=energy_density_absorbed_by_CMB()
    specific_energy = np.repeat(energy_density_absorbed.value,dustdens.shape)


    ''' #debug and remove this after testing is done'''
    if cfg.par.otf_extinction == False:
        
        if cfg.par.PAH == True:
        
            # load PAH fractions for usg, vsg, and big (grain sizes)
            frac = cfg.par.PAH_frac
            
            # Normalize to 1
            total = np.sum(list(frac.values()))
            frac = {k: v / total for k, v in frac.items()}

            for size in frac.keys():
                d = SphericalDust(cfg.par.dustdir+'%s.hdf5'%size)
                if cfg.par.SUBLIMATION == True:
                    d.set_sublimation_temperature('fast',temperature=cfg.par.SUBLIMATION_TEMPERATURE)
            #m.add_density_grid(dustdens * frac[size], cfg.par.dustdir+'%s.hdf5' % size)
            m.add_density_grid(dustdens*frac[size],d,specific_energy=specific_energy)
            m.set_enforce_energy_range(cfg.par.enforce_energy_range)
        else:
            d = SphericalDust(cfg.par.dustdir+cfg.par.dustfile)
            if cfg.par.SUBLIMATION == True:
                d.set_sublimation_temperature('fast',temperature=cfg.par.SUBLIMATION_TEMPERATURE)
            m.add_density_grid(dustdens,d,specific_energy=specific_energy)
        #m.add_density_grid(dustdens,cfg.par.dustdir+cfg.par.dustfile)  


    else: #instead of using a constant extinction law across the
          #entire galaxy, we'll compute it on a cell-by-cell basis by
          #using information about the grain size distribution from
          #the simulation itself.


        print("==============================================\n")
        print("Entering OTF Extinction Calculation\n")
        print("Note: For very high-resolution grids, this may cause memory issues due to adding ncells dust grids")
        print("==============================================\n")
        
        ad = ds.all_data()
        nsizes = ad['PartType3','Dust_Size'].shape[1]
        ncells = reg.parameters["octree_of_sizes"].shape[0]
        #ensure that the grid has particles
        for isize in range(nsizes):
            try:
                assert (np.sum(reg.parameters["octree_of_sizes"][:,isize]) > 0)
            except AssertionError:
                raise AssertionError("[sph_tributary:] The grain size distribution smoothed onto the octree has deposited no particles.  Try either increasing your box size, or decreasing n_ref in parameters_master.  Alternatively, run the simulation with otf_extinction=False")

        #for empty cells, use the median size distribution
        for isize in range(nsizes):
            wzero = np.where(reg.parameters["octree_of_sizes"][:,isize] == 0)[0]
            wnonzero = np.where(reg.parameters["octree_of_sizes"][:,isize] != 0)[0]

            reg.parameters['octree_of_sizes'][wzero,isize] = np.median(reg.parameters['octree_of_sizes'][wnonzero,isize])

            print(len(wzero)/len(wnonzero))


        #TO DO TO DO TO DO now that the octree is populated with
        #grains, fit the size distribution in each cell to a degree 3
        #polynomial (ax^3 + bx^2 + cx + d), and then bin these (a->d)
        #parameters.  we then add a grid for each of these parameter
        #combinations, and for each bin size 

        


        #now load the mapping between grain bin and filename for the lookup table
        data = np.load(cfg.par.pd_source_dir+'active_dust/dust_files/binned_dust_sizes.npz')
        grain_size_left_edge_array = data['grain_size_left_edge_array']
        grain_size_right_edge_array  = data['grain_size_right_edge_array']
        dust_filenames = data['outfile_filenames']

        nbins = len(grain_size_left_edge_array)


        #find which sizes in the hydro simulation correspond to the
        #pre-binned extinction law sizes from dust_file_writer.py

        dust_file_to_grain_size_mapping_idx = []
        x=np.linspace(cfg.par.otf_extinction_log_min_size,cfg.par.otf_extinction_log_max_size,nsizes)
        for i in range(nbins):
            dust_file_to_grain_size_mapping_idx.append(find_nearest(x,grain_size_left_edge_array[i]))


        #set up the frac arrays that are dustdens,nbins big 
        frac = np.zeros([dustdens.shape[0],nbins])

        #temp_frac is the frac at the WFalse points (i.e., where we
        #have computed the octree_of_sizes in the front end). we do
        #the computing here, and then stuff this into the wFalse cells
        #of frac
        temp_frac = np.empty(reg.parameters['octree_of_sizes'].shape[0]) 

        wFalse = np.where(np.asarray(refined) == 0)[0]

        for bin in range(nbins):
            temp_frac = reg.parameters['octree_of_sizes'][:,dust_file_to_grain_size_mapping_idx[bin]]
            frac[wFalse,bin] = temp_frac

            file = dust_filenames[bin]

            d = SphericalDust(cfg.par.pd_source_dir+'active_dust/'+file)
            m.add_density_grid(dustdens*frac[:,bin],d,specific_energy=specific_energy)
            
            

        

        '''
        #now loop through the cells in the octree, and create a frac *
        #dustdens for each cell density grid, and add that density
        #grid.  this means we add ncells density grids NOTE: THIS
        #COULD END UP BEING A MEMORY PROBLEM FOR VERY HIGH-RES SIMS.

        frac = np.empty(nbins)

        false_counter = 0
        for icell in range(len(dustdens)):
            print(icell)
            if refined[icell] == False:
                frac = reg.parameters['octree_of_sizes'][false_counter]
                #normalize
                frac/=np.sum(frac)
                
                false_counter +=1


                #now make a dust grid that just has 1 cell with
                #information in it, and add these in sequence with the
                #grain size fractions weighted according to the size
                #distribution in that cell
                dustdens_onecell = dustdens*0
                dustdens_onecell[icell] = dustdens[icell]
                

                for counter,file in enumerate(dust_filenames):
                    d = SphericalDust(cfg.par.pd_source_dir+'active_dust/'+file)
                    m.add_density_grid(dustdens_onecell*frac[dust_file_to_grain_size_mapping_idx[counter]],d,specific_energy=specific_energy)
                    
        '''
        

        


    #TESTING BLOCK ONLY - MUCH OF THIS NEEDS TO BE REMOVED
    '''
    #load the mapping between grain bin and filename
    data = np.load(cfg.par.pd_source_dir+'active_dust/dust_files/binned_dust_sizes.npz')
    grain_size_left_edge_array = data['grain_size_left_edge_array']
    grain_size_right_edge_array  = data['grain_size_right_edge_array']
    dust_filenames = data['outfile_filenames']


    #how DNSF was set up.  not needed other than for testing
    x=np.linspace(-4,0,41)
    #load an example dust size function for testing against
    dsf = np.loadtxt(cfg.par.pd_source_dir+'active_dust/mrn_dn.txt')#DNSF_example.txt')

    nbins = len(grain_size_left_edge_array)
    frac = np.empty(nbins)
    for i in range(nbins):
        idx = find_nearest(x,grain_size_left_edge_array[i])
        
        #this sets the fraction of each bin size we need (for the
        #entire grid! this eventually needs to be cell by cell)
        frac[i] = dsf[idx]

    # Normalize to 1
    total = np.sum(frac)
    frac/=total
    
    for counter,file in enumerate(dust_filenames):
        d = SphericalDust(cfg.par.pd_source_dir+'active_dust/'+file)
        m.add_density_grid(dustdens*frac[counter],d,specific_energy=specific_energy)

    '''
    
    





    m.set_specific_energy_type('additional')








    return m,xcent,ycent,zcent,dx,dy,dz,reg,ds,boost
