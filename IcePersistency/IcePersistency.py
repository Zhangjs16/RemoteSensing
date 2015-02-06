
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 26 08:18:31 2014
@author: max
 
Creating ice persistency maps from NSIDC sea ice concentration charts
* Bin2GeoTiff -- converting binary NSIDC maps to GeoTIFF
* CreateIcePercistanceMap -- create ice persistence map
* CreateMaxMinIce -- create min/max ice maps
* EPSG3411_2_EPSG3575 -- reproject raster from EPSG:3411 to EPSG:3575
* ReprojectShapefile -- reproject shapefiles from EPSG:3411 to EPSG:3575
Documentation before each function and at https://github.com/npolar/RemoteSensing/wiki/Sea-Ice-Frequency
"""

import struct, numpy, gdal, gdalconst, glob, os, osr, datetime, subprocess, shutil

def EPSG3411_2_EPSG3575(infile):
    '''
    reprojects the infile from NSIDC 3411 to EPSG 3575
    outputfile has 25km resolution
    '''
    
    (infilepath, infilename) = os.path.split(infile)
    (infileshortname, extension) = os.path.splitext(infilename)
    outdirectory = infilepath + '\\EPSG3575\\'
    if not os.path.exists(outdirectory):
        os.makedirs(outdirectory)
    outfile =  outdirectory + infileshortname + '_EPSG3575.tif'
    print ' Reproject ', infile, ' to ', outfile 
    os.system('gdalwarp -s_srs EPSG:3411 -tr 25000 -25000 -t_srs EPSG:3575 -of GTiff ' + infile + ' ' + outfile)
    
def ReprojectShapefile(infile, inproj = "EPSG:3411", outproj = "EPSG:3575"):
    '''
    Reprojects the shapefile given in infile
    
    inproj and outproj in format "EPSG:3575", for the filename the ":" is 
    removed in the function
    
    Assumes existence of folder as "EPSG3575" or "EPSG32633" or...
    '''
    
    #Define outputfile name
    (infilepath, infilename) = os.path.split(infile)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    
    reprshapepath = infilepath + '\\' + outproj[0:4] + outproj[5:9]
    reprshapeshortname = infileshortname + '_' + outproj[0:4] + outproj[5:9]
    reprshapefile = reprshapepath + '\\'+ reprshapeshortname + extension
    
    #Reproject using ogr commandline
    print 'Reproject Shapefile ', infile    
    os.system('ogr2ogr -s_srs ' + inproj + ' -t_srs ' + outproj + ' '  + reprshapefile + ' ' + infile )
    print 'Done Reproject'

    return reprshapefile    

def Bin2GeoTiff(infile,outfilepath ):
    '''
        This function takes the NSIDC charts, being a flat binary string, and converts them to GeoTiff. Some details here:
        http://geoinformaticstutorial.blogspot.no/2014/02/reading-binary-data-nsidc-sea-ice.html
        Info on the ice concentration charts: http://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html 
        Info on the map projection: http://nsidc.org/data/polar_stereo/ps_grids.html
        The GeoTiff files are map projected to EPSG:3411, being the NSIDC-specific projection.
        There also is produced a GeoTiff reprojected to EPSG:3575 which is the NP-standard for Barents/Fram-Strait.
        Details on how to map project are found here:
        http://geoinformaticstutorial.blogspot.no/2014/03/geocoding-nsidc-sea-ice-concentration.html
        
    '''
    
    #Define file names 
    (infilepath, infilename) = os.path.split(infile)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
        
    outfile = outfilepath + infileshortname + '.tif'
    #Dimensions from https://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html
    height = 448
    width = 304
    
    #####    
    # READ FLAT BINARY INTO ARRAY
    #####
    #for this code on how to read flat binary string, inspiration found at https://stevendkay.wordpress.com/category/python/
    icefile = open(infile, "rb")
    contents = icefile.read()
    icefile.close()
    
    # unpack binary data into a flat tuple z
    #offset and width/height from https://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html
    s="%dB" % (int(width*height),)
    z=struct.unpack_from(s, contents, offset = 300) 
    nsidc = numpy.array(z).reshape((448,304))
    
    ########
    #WRITE THE ARRAY TO GEOTIFF
    ########
    driver = gdal.GetDriverByName("GTiff")
    outraster = driver.Create(outfile,  width, height,1, gdal.GDT_Int16 )
    if outraster is None: 
        print 'Could not create '
        return
    
    #set geotransform, values from https://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html
    geotransform = (-3850000.0, 25000.0 ,0.0 ,5850000.0, 0.0, -25000.0)
    outraster.SetGeoTransform(geotransform)
    outband = outraster.GetRasterBand(1)
    #Write to file     
    outband.WriteArray(nsidc)
    
    spatialRef = osr.SpatialReference()
    #spatialRef.ImportFromEPSG(3411)  --> this one does for some reason NOT work, but using proj4 does
    spatialRef.ImportFromProj4('+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +a=6378273 +b=6356889.449 +units=m +no_defs')
    outraster.SetProjection(spatialRef.ExportToWkt() )
    outband.FlushCache()
    
    #Clear arrays and close files
    outband = None
    outraster = None
    nsidc = None
    
    #####
    #REPROJECT GEOTIFF TO EPSG3575
    #####
    EPSG3411_2_EPSG3575(outfile)

def CopyNonIceValues(inputRaster, outputRaster, maskList = [251, 252, 253, 254, 255]):
    '''
    Copies the non ice values of the inputArray into the outputArray. Mask values are
    defined by the maskValues list. If maskValues isn't defined it we'll use the
    default nsidc mask values defined in the "parameter or variable" section @
    http://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html
    '''

    for maskVal in maskList:
        outarray = numpy.where( (inputRaster == maskVal), maskVal, outputRaster)

    return outputRaster

def GenerateTemporaryShapefileDict(filepath, basename="tmpShape", numberOfTmpFiles=3):
    tmpShapeFiles = {}
    shapeFileExtensions = [".shp", ".shx", ".dbf", ".prj"]

    for count in range(1, numberOfTmpFiles + 1):
        for ext in shapeFileExtensions:
            tmpMax = basename + count + "max" + ext
            tmpMin = basename + count + "min" + ext

            tmpShapeFiles[tmpMax] = filepath + tmpMax
            tmpShapeFiles[tmpMin] = filepath + tmpMin

    return tmpShapeFiles

# Removes files defined in a dictionary from the filesystem
def RemoveFilesByDictionary(fileDictionary):
    for key in fileDictionary.iterkeys():
        # Check if file exists before we try to remove it
        if os.path.isfile(fileDictionary[key]):
            os.remove(fileDictionary[key])
    
def CreateIcePercistanceMap(inpath, outfilepath, max_ice, min_ice, landmask_raster):
    '''
    Creates map showing percentage ice coverage over a given period
    This function creates the ice persistence charts. 
    The function loops through each concentration map, if the value is larger
    than 38 = 15.2%, the value of "100.0 / NumberOfDays" is added --> if there 
    is ice every single day, that pixel will be "100"
    Output is available both as EPSG:3411 and EPSG:3575    
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    # filelist is all GeoTIFF files created in outfilepath
    filelist = glob.glob(outfilepath + 'nt*.tif')
    
    #Determine Number of Days from available ice chart files
    NumberOfDays = len(filelist)
    
    
    firstfilename = filelist[0]
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
        
    outfile = inpath + 'icechart_persistencemap' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.tif'
    
    ########
    # CREATE OUTPUT FILE AS COPY FROM ONE ICECHART
    ########
    
    #open the IceChart
    icechart = gdal.Open(firstfilename, gdalconst.GA_ReadOnly)
    if firstfilename is None:
        print 'Could not open ', firstfilename
        return
    #get image size
    rows = icechart.RasterYSize
    cols = icechart.RasterXSize    
    #create output images
    driver = icechart.GetDriver()
    outraster = driver.Create(outfile, cols, rows, 1, gdal.GDT_Float64 )
    if outraster is None: 
        print 'Could not create ', outfile
        return
    
    # Set Geotransform and projection for outraster
    outraster.SetGeoTransform(icechart.GetGeoTransform())
    outraster.SetProjection(icechart.GetProjection())
    
    rows = outraster.RasterYSize
    cols = outraster.RasterXSize
    raster = numpy.zeros((rows, cols), numpy.float) 
    outraster.GetRasterBand(1).WriteArray( raster )
    
    #Create output array and fill with zeros
    outarray = numpy.zeros((rows, cols), numpy.float)    
    
    #######
    # CALCULATE ICE PERSISTENCE RASTER
    #######
    
    #Loop through all files to do calculation
    for infile in filelist:
        
        (infilepath, infilename) = os.path.split(infile)
        print 'Processing ', infilename
        
        #open the IceChart
        icechart = gdal.Open(infile, gdalconst.GA_ReadOnly)
        if infile is None:
            print 'Could not open ', infilename
            return
        
        #get image size
        rows = icechart.RasterYSize
        cols = icechart.RasterXSize
                
        #get the bands 
        outband = outraster.GetRasterBand(1)
                
        #Read input raster into array
        iceraster = icechart.ReadAsArray()
        
        #Array calculation and burn in land values on top
        outarray = numpy.where( (iceraster >=  38), (outarray + ( 100.0 / NumberOfDays ) ) , outarray)
        outarray = CopyNonIceValues(iceraster, outarray)
               
        #Clear iceraster for next loop -- just in case
        iceraster = None
        
    ######
    # Filter noise areas
    ######

    #Filter with maximum map since persistance map has noise values just as max map.
    #FUNCTION CreateMaxMinIce  HAS TO BE RUN BEFORE CreateIcePercistanceMap
    max_chart = gdal.Open(max_ice, gdalconst.GA_ReadOnly)
    max_chartraster = max_chart.ReadAsArray()
    landmask = gdal.Open(landmask_raster, gdalconst.GA_ReadOnly)
    landraster = landmask.ReadAsArray()

    outarray = numpy.where(max_chartraster == 1, outarray, 0)
    outarray = CopyNonIceValues(landraster, outarray)
    
    outband = outraster.GetRasterBand(1)   
    outband.WriteArray(outarray)
    outband.FlushCache()
       
    #Clear arrays and close files
    outband = None
    iceraster = None
    outraster = None
    outarray = None
    
    #####
    #REPROJECT GEOTIFF TO EPSG3575
    #####
    EPSG3411_2_EPSG3575(outfile)
    
    return outfile
    print 'Done Creating Persistence Map'
    


def CreateMaxMinIce(inpath, outfilepath, landmask_raster, coastalerrormask_raster, oceanmask_buffer5, NSIDC_balticmask ):   
    ''' 
         Creates maximum and minimum ice map, GeoTIFF and shapefile
         maximum = at least one day ice at this pixel
         minimum = every day ice at this pixel
         In addition a file simply giving the number of days with ice
         
         The poly shapefile has all features as polygon, the line shapefile
         only the max or min ice edge
    
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    # filelist is all GeoTIFF files created in outfilepath
    filelist = glob.glob(outfilepath + 'nt*.tif')
    
    #Determine Number of Days from available ice chart files
    NumberOfDays = len(filelist)
    
    #Files are all the same properties, so take first one to get info
    firstfilename = filelist[0]
    
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    
    outfile =  inpath + 'icechart_NumberOfDays' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.tif'
    outfilemax = inpath + 'icechart_maximum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.tif'
    outfilemin = inpath + 'icechart_minimum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.tif'
    
    outshape_polymax = inpath + 'icechart_poly_maximum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.shp'
    outshape_polymin = inpath + 'icechart_poly_minimum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.shp'
    outshape_linemax = inpath + 'icechart_line_maximum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.shp'
    outshape_linemin = inpath + 'icechart_line_minimum' + filelist[0][-22:-16] + '_' + filelist[-1][-22:-16] + '.shp'

    ########
    # CREATE NUMBER OF DAYS RASTER FILE AS COPY FROM ICE FILE
    ########    
    #open the IceChart
    icechart = gdal.Open(firstfilename, gdalconst.GA_ReadOnly)
    if firstfilename is None:
        print 'Could not open ', firstfilename
        return
    #get image size
    rows = icechart.RasterYSize
    cols = icechart.RasterXSize    
    #create output images
    driver = icechart.GetDriver()
    outraster = driver.Create(outfile, cols, rows, 1, gdal.GDT_Float64 )
    if outraster is None: 
        print 'Could not create ', outfile
        return    
    
    outrastermax = driver.Create(outfilemax, cols, rows, 1, gdal.GDT_Float64 )
    if outrastermax is None: 
        print 'Could not create ', outfilemax
        return
    
    outrastermin = driver.Create(outfilemin, cols, rows, 1, gdal.GDT_Float64 )
    if outrastermin is None: 
        print 'Could not create ', outfilemin
        return
   
    # Set Geotransform and projection for outraster
    outraster.SetGeoTransform(icechart.GetGeoTransform())
    outraster.SetProjection(icechart.GetProjection())
    outrastermax.SetGeoTransform(icechart.GetGeoTransform())
    outrastermax.SetProjection(icechart.GetProjection())
    
    outrastermin.SetGeoTransform(icechart.GetGeoTransform())
    outrastermin.SetProjection(icechart.GetProjection())
    
    rows = outrastermax.RasterYSize
    cols = outrastermax.RasterXSize
    raster = numpy.zeros((rows, cols), numpy.float) 
    
    outraster.GetRasterBand(1).WriteArray( raster )    
    outrastermax.GetRasterBand(1).WriteArray( raster )
    outrastermin.GetRasterBand(1).WriteArray( raster )
    
    #Create output array and fill with zeros
    outarray = numpy.zeros((rows, cols), numpy.float)    
    outarraymax = numpy.zeros((rows, cols), numpy.float)
    outarraymin = numpy.zeros((rows, cols), numpy.float)
    
    #######
    # CALCULATE NUMBER OF DAYS RASTER = NUMBER SAYS HOW MANY DAYS ICE IN PIXEL
    #######
    #Loop through all files to do calculation
    for infile in filelist:
        
        (infilepath, infilename) = os.path.split(infile)
        print 'Processing ', infilename
        
        #open the IceChart
        icechart = gdal.Open(infile, gdalconst.GA_ReadOnly)
        if infile is None:
            print 'Could not open ', infilename
            return
        
        #Read input raster into array
        iceraster = icechart.ReadAsArray()
        
        #Array calculation -- if ice > 15% count additional day, otherwise keep value
        outarray = numpy.where( (iceraster >=  38), outarray + 1 , outarray)
                       
        #Clear iceraster for next loop -- just in case
        iceraster = None
    
    
    
    
    #outarray contains now NumberOfDay with ice -- burn in landmask
    landmask = gdal.Open(landmask_raster , gdalconst.GA_ReadOnly)
    landraster = landmask.ReadAsArray()

    outarray = CopyNonIceValues(landraster, outarray)
    
    #######
    # CALCULATE MAXIMUM RASTER
    #######
    # Where never was ice, set map to 0, elsewhere to 1, i.e. at least one day ice
    # Using landraster again -- otherwise if NumberOfDay mask by chance 252, it is masked out
    outarraymax = numpy.where( (outarray == 0), 0, 1 )

    outarraymax = CopyNonIceValues(landraster, outarraymax)
    
    #######
    # CALCULATE MINIMUM RASTER
    #######
    # Where every day was ice, set to 1, otherwise to 0
    # Keep in mind: Problems may arise when one value is missing (bad file)
    # such that value is just one or two less than NumberofDays
    outarraymin = numpy.where( (outarray == NumberOfDays), 1, 0 )
    outarraymin = CopyNonIceValues(landraster, outarraymin)
        
    #get the bands 
    outband = outraster.GetRasterBand(1)    
    outbandmax = outrastermax.GetRasterBand(1)
    outbandmin = outrastermin.GetRasterBand(1)
    
    
    #Write all arrays to file
    
    outband.WriteArray(outarray)
    outband.FlushCache()    
    
    outbandmax.WriteArray(outarraymax)
    outbandmax.FlushCache()
    
    outbandmin.WriteArray(outarraymin)
    outbandmin.FlushCache()
    
    ##########
    # FILTER NOISE IN MINIMUM ARRAY / RASTER
    #########
    # the sieve filter takes out singular "islands" of pixels
    srcband = outbandmin
    dstband = outbandmin    
    maskband = None
    print "Apply SieveFilter on ", outfilemin
    gdal.SieveFilter( srcband, maskband, dstband,threshold = 3, connectedness = 4  )
    #load outbandmin once more and burn landmask again since sieve influences coastline
    outarraymin = outrastermin.ReadAsArray()
    outarraymin = CopyNonIceValues(landraster, outarraymin)

    outbandmin = outrastermin.GetRasterBand(1)    
    outbandmin.WriteArray(outarraymin)
    outbandmin.FlushCache()
    
    ##########
    # FILTER NOISE IN MINIMUM ARRAY / RASTER
    #########    
    # the sieve filter takes out singular "islands" of pixels
    srcband = outbandmax
    dstband = outbandmax    
    maskband = None
    print "Apply SieveFilter one ", outrastermax
    gdal.SieveFilter( srcband, maskband, dstband,threshold = 3, connectedness = 4  )
    #load outbandmin once more and burn landmask again since sieve influences coastline
    outarraymax = outrastermax.ReadAsArray()

    # NOTE!!! Is there a reason why the missing data mask is ignored here?
    outarraymax = CopyNonIceValues(landraster, outarraymax, [251, 252, 253, 254])

    outbandmax = outrastermax.GetRasterBand(1)    
    outbandmax.WriteArray(outarraymax)
    outbandmax.FlushCache()
    
    #Clear arrays and close files
    outband = None
    outbandmax = None
    outbandmin = None
    iceraster = None
    outraster = None    
    outrastermax = None
    outrastermin = None
    outarray = None
    outarraymax = None
    outarraymin = None   
    landraster = None   
    landmask = None     

    ##################
    # Create the shape files needed for the conversion operation
    #################
    # Temporary shapefile, all subfiles specified so that they can be removed later
    # Many because gdal commands expect existing files
    tmpShapeFiles = GenerateTemporaryShapefileDict(inpath, "icechart_temp")

    ###################
    # CONVERT THE RASTERS CREATED ABOVE TO SHAPEFILES
    ###################

    # conversion to shape    
    print '\n Convert ', outfilemax, ' to shapefile.'
    os.system('gdal_polygonize.py ' + outfilemax + ' -f "ESRI Shapefile" ' + tmpShapeFiles["icechart_temp1max.shp"] )
    print '\n Convert ', outfilemin, ' to shapefile.'
    os.system('gdal_polygonize.py ' + outfilemin + ' -f "ESRI Shapefile" ' + tmpShapeFiles["icechart_temp1min.shp"] ) 
    
    # FILTERING MAX / MIN    
    # Get the large polygon only, this removes mistaken areas at coast and noise. KEEP IN MIND: CHECK VALUE IF TOO BIG SUCH THAT REAL AREAS ARE REMOVED
    # Do this only for polymax -- the minimum would remove real areas, patches like East of Svalbard. Polymin selects here all polygons basically
    print "Select large polygon, ignoring the small ones"
    os.system('ogr2ogr -progress '+ outshape_polymax + ' ' + tmpShapeFiles["icechart_temp1max.shp"] + ' -sql "SELECT *, OGR_GEOM_AREA FROM icechart_tempmax WHERE DN=1 AND OGR_GEOM_AREA > 10000000000.0"')
    os.system('ogr2ogr -progress '+ outshape_polymin + ' ' + tmpShapeFiles["icechart_temp1min.shp"] + ' -sql "SELECT *, OGR_GEOM_AREA FROM icechart_tempmin WHERE DN=1 AND OGR_GEOM_AREA > 10.0"')
    
    # Convert polygon to lines
    print 'Convert ice edge map to Linestring Map'
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + tmpShapeFiles["icechart_temp2max.shp"] + ' ' + outshape_polymax)
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + tmpShapeFiles["icechart_temp2min.shp"] + ' ' + outshape_polymin)
    
    # Remove coast line from ice edge by clipping with coastline
    # Prerequisite: Create NISDC coast line mask ( ogr2ogr -progress C:\Users\max\Desktop\NSIDC_oceanmask.shp C:\Users \max\Desktop\temp.shp
    # -sql "SELECT *, OGR_GEOM_AREA FROM temp WHERE DN<250 )
    # use "dissolve" to get ocean only with one value and the run buffer -5000m such that coast line does not match but overlaps ice polygon
    # because only then it is clipped
    os.system('ogr2ogr -progress -clipsrc ' + oceanmask_buffer5 + ' ' +  outshape_linemax + ' ' + tmpShapeFiles["icechart_temp2max.shp"])
    os.system('ogr2ogr -progress -clipsrc ' + oceanmask_buffer5 + ' ' +  outshape_linemin + ' ' + tmpShapeFiles["icechart_temp2min.shp"])

    ############
    # Clean Temporary ShapeFiles
    ############

    RemoveFilesByDictionary(tmpShapeFiles)
    
    ##########
    # ADDING BALTIC SEA
    ##########
    
    #Treated separatedly since close to coast and therefore sensitive to coastal errors
    print '\n Add Baltic Sea Ice.'
    
    #polygonice only Baltic Sea
    os.system('gdal_polygonize.py ' + outfilemax + ' -mask ' + NSIDC_balticmask + ' -f "ESRI Shapefile" ' + tmpShapeFiles["icechart_temp1max.shp"] )    
    os.system('gdal_polygonize.py ' + outfilemin + ' -mask ' + NSIDC_balticmask + ' -f "ESRI Shapefile" ' + tmpShapeFiles["icechart_temp1min.shp"] )    
        
    # Add Baltic to existing polymax and polymin 
    os.system('ogr2ogr -update -append ' + outshape_polymax + ' ' +   tmpShapeFiles["icechart_temp1max.shp"] +  ' -sql "SELECT *, OGR_GEOM_AREA FROM icechart_tempmax WHERE DN=1 AND OGR_GEOM_AREA > 20000000000.0"')
    os.system('ogr2ogr -update -append ' + outshape_polymin + ' ' +   tmpShapeFiles["icechart_temp1min.shp"] +  ' -sql "SELECT *, OGR_GEOM_AREA FROM icechart_tempmin WHERE DN=1"')
    
    # Convert polygon to lines
    print 'Convert ice edge map to Linestring Map'
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + tmpShapeFiles["icechart_temp2max.shp"] + ' ' + outshape_polymax)
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + tmpShapeFiles["icechart_temp2min.shp"] + ' ' + outshape_polymin)
    
    #clip coast as above
    os.system('ogr2ogr -progress -clipsrc ' + oceanmask_buffer5 + ' ' +  tmpShapeFiles["icechart_temp3max.shp"] + ' ' + tmpShapeFiles["icechart_temp2max.shp"])
    os.system('ogr2ogr -progress -clipsrc ' + oceanmask_buffer5 + ' ' +  tmpShapeFiles["icechart_temp3min.shp"] + ' ' + tmpShapeFiles["icechart_temp2min.shp"])
    
    # Add Baltic line to existing min/max line
    os.system('ogr2ogr -update -append ' + outshape_linemax + ' ' +   tmpShapeFiles["icechart_temp3max.shp"] )
    os.system('ogr2ogr -update -append ' + outshape_linemin + ' ' +   tmpShapeFiles["icechart_temp3min.shp"] )

    ####################
    # Clean Temporary ShapeFiles
    ###################
    RemoveFilesByDictionary(tmpShapeFiles)

    #########
    # REDO MAX MIN RASTER
    #########    
    
    #The polygon and line files are now cleaned for noise since only large polygon
    # was chosen for minimum polygon
    # Re-rasterize to tif, such that the tiff is also cleaned

    # gdal rasterize should be able to overwrite / create new a file. Since this does not work, I set the
    # existing one to zero and rasterize the polgon into it
    print 'Rerasterize max and min GeoTIFF'
    outarray = gdal.Open( outfilemax, gdalconst.GA_Update)
    outarraymax = outarray.ReadAsArray()
    outarraymax = numpy.zeros((rows, cols), numpy.float) 
    outbandmax = outarray.GetRasterBand(1)    
    outbandmax.WriteArray(outarraymax)
    outbandmax.FlushCache()
    outarray = None
    
    #Rasterize polygon
    subprocess.call('gdal_rasterize -burn 1 ' + outshape_polymax + ' ' + outfilemax )
    # OPen raster and burn in landmask again -- is not contained in polygon
    outarray = gdal.Open( outfilemax, gdalconst.GA_Update)
    outarraymax = outarray.ReadAsArray()
    landmask = gdal.Open(landmask_raster, gdalconst.GA_ReadOnly)
    landraster = landmask.ReadAsArray()

    outarraymax = CopyNonIceValues(landraster, outarraymax)

    outbandmax = outarray.GetRasterBand(1)    
    outbandmax.WriteArray(outarraymax)
    outbandmax.FlushCache()
    outarray = None
    landmask = None
    landraster = None
    
    #Reraster the min image
    outarray = gdal.Open( outfilemin, gdalconst.GA_Update)
    outarraymin = outarray.ReadAsArray()
    outarraymin = numpy.zeros((rows, cols), numpy.float) 
    outbandmin = outarray.GetRasterBand(1)    
    outbandmin.WriteArray(outarraymin)
    outbandmin.FlushCache()
    outarray = None
    #Rasterize polygon
    subprocess.call('gdal_rasterize -burn 1 ' + outshape_polymin + ' ' + outfilemin )
    # OPen raster and burn in landmask again -- is not contained in polygon
    outarray = gdal.Open( outfilemin, gdalconst.GA_Update)
    outarraymin = outarray.ReadAsArray()
    landmask = gdal.Open(landmask_raster, gdalconst.GA_ReadOnly)
    landraster = landmask.ReadAsArray()

    outarraymax = CopyNonIceValues(landraster, outarraymin)

    outbandmin = outarray.GetRasterBand(1)    
    outbandmin.WriteArray(outarraymin)
    outbandmin.FlushCache()
    landmask = None
    landraster = None

    #Reproject to EPSG:3575
    ReprojectShapefile(outshape_polymax)
    ReprojectShapefile(outshape_polymin)
    ReprojectShapefile(outshape_linemax)
    ReprojectShapefile(outshape_linemin)
  
    #reproject to EPSG3575
    EPSG3411_2_EPSG3575(outfilemax)        
    EPSG3411_2_EPSG3575(outfilemin) 
    EPSG3411_2_EPSG3575(outfile) 
    print    
    print 'Done Creating Max/Min Maps'        
    return outfilemax, outfilemin
    
def FilterCoastalAreas(outfilepath, landmask_raster, coastalerrormask_raster):
    '''
    Problem: Along Coastal Areas, the land/ocean boundary appears as ice values
    Solution: Mask for problematice areas, but consider as ice if value remains
    for a number of consecutive days -- filters singular error pixels
    
    Loop through all NSIDC ice concentration areas
    In the coastal areas (defined by NSIDC_coastalerrormask_raster.tif) ice concentration
    above 15% is only considered if ice is present three days before and after the date
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    filelist = glob.glob(outfilepath + 'nt*.tif')
    
    
    #Files are all the same properties, so take first one to get info
    firstfilename = filelist[0]
    
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    

    
    #Open Coastal Mask into array
    #THe coastal mask defines error areas -- value 1 for coast, value 2 for Baltic and value 3 for never-ice areas.
    coastalerrormask = gdal.Open(coastalerrormask_raster, gdalconst.GA_ReadOnly)
    coastalerrormaskarray = coastalerrormask.ReadAsArray()
    
    #Create file receiving the ice mask
    #get image size
    rows = coastalerrormask.RasterYSize
    cols = coastalerrormask.RasterXSize   
    
    coastalicemaskraster = numpy.zeros((rows, cols), numpy.float) 
    #Loop through all files to do calculation
    for infile in filelist:
        #Find present data    
        presentyear = int(infile[-22:-18])
        presentmonth = int(infile[-18:-16])
        presentday = int(infile[-16:-14])
        
        presentdate =  datetime.date(presentyear, presentmonth, presentday) 
        
        ########################
        # COASTAL ERROR FOR COAST
        ########################        
        # ADJUST HOW MANY DAYS PLUS AND MINUS THE PRESENT DATE YOU WANT
        dayrange = 2
        
        #Let ice value in coastal zone persist if there was ice the days around it
        presentdayfilename = outfilepath + "nt_" + presentdate.strftime('%Y%m%d') +  infile[-14:]
        presentdayfile = gdal.Open( presentdayfilename, gdalconst.GA_Update)
        presentdayraster = presentdayfile.ReadAsArray()
        print "coastal error mask for ", presentdayfilename
        #Reset coastalicemaskraster to zero
        coastalicemaskraster = numpy.zeros((rows, cols), numpy.float) 
        #Loop through the files around present day and determine how many days there is ice in coastal zone    
        for i in range(-dayrange, dayrange +1):
            diff = datetime.timedelta(days=i)
            diffdate = presentdate + diff
            checkfilename = outfilepath + "nt_" + diffdate.strftime('%Y%m%d') +  infile[-14:]
            
            if os.path.isfile(checkfilename):
                checkfile = gdal.Open(checkfilename, gdalconst.GA_ReadOnly)
                #Read input raster into array
                checkfileraster = checkfile.ReadAsArray()
                coastalicemaskraster = numpy.where( (coastalerrormaskarray == 1) & (checkfileraster >= 38), coastalicemaskraster + 1 , coastalicemaskraster )
                
                
            else:
                #If previous day files do not exist, take present day one -- otherwise it does not add up with number of Days                
                coastalicemaskraster = numpy.where( (coastalerrormaskarray == 1) & (presentdayraster >= 38), coastalicemaskraster + 1 , coastalicemaskraster )
                
        

        
        presentdayraster = numpy.where( (coastalerrormaskarray == 1) & ( coastalicemaskraster < 5 ), 0, presentdayraster)
        ########################
        # COASTAL ERROR FOR DEFINITE NO ICE AREAS
        ########################       
        presentdayraster = numpy.where( (coastalerrormaskarray == 3), 0, presentdayraster)
        
        
        ########################
        # COASTAL ERROR FOR BALTIC
        ########################
        dayrange = 2
        #Reset coastalicemaskraster to zero
        coastalicemaskraster = numpy.zeros((rows, cols), numpy.float) 
        #Loop through the files around present day and determine how many days there is ice in coastal zone    
        for i in range(-dayrange, dayrange +1):
            diff = datetime.timedelta(days=i)
            diffdate = presentdate + diff
            checkfilename = outfilepath + "nt_" + diffdate.strftime('%Y%m%d') +  infile[-14:]
            
            if os.path.isfile(checkfilename):
                checkfile = gdal.Open(checkfilename, gdalconst.GA_ReadOnly)
                #Read input raster into array
                checkfileraster = checkfile.ReadAsArray()
                
                coastalicemaskraster = numpy.where( (coastalerrormaskarray == 2) & (checkfileraster >= 38), coastalicemaskraster + 1 , coastalicemaskraster )
            else:
                #If previous day files do not exist, take present day one -- otherwise it does not add up with number of Days                
                
                coastalicemaskraster = numpy.where( (coastalerrormaskarray == 2) & (presentdayraster >= 38), coastalicemaskraster + 1 , coastalicemaskraster )
                
                
        

        # coastalicemaskraster < 5 or rather a value of 4 should be considered in future checks
        presentdayraster = numpy.where( (coastalerrormaskarray == 2) & (coastalicemaskraster < 5 ), 0, presentdayraster)
                
        # outarray contains filtered values -- burn in landmask
        landmask = gdal.Open(landmask_raster, gdalconst.GA_ReadOnly)
        landraster = landmask.ReadAsArray()

        presentdayraster = CopyNonIceValues(landraster, presentdayraster)

        presentdayfileband = presentdayfile.GetRasterBand(1)
            
        presentdayfileband.WriteArray(presentdayraster)
        presentdayfileband.FlushCache()
    
    
    
        
def FilterConsecDays(outfilepath, landmask_raster, coastalerrormask_raster):
    '''
    Problem: Along Coastal Areas, the land/ocean boundary appears as ice values
    Solution: Mask for problematice areas, but consider as ice if value remains
    for a number of consecutive days -- filters singular error pixels
    
    Loop through all NSIDC ice concentration areas
    In the coastal areas (defined by NSIDC_coastalerrormask_raster.tif) ice concentration
    above 15% is only considered if ice is present three days before and after the date
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    filelist = glob.glob(outfilepath + 'nt*.tif')
    
    
    #Files are all the same properties, so take first one to get info
    firstfilename = filelist[0]
    
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    

    
    #Open Coastal Mask into array
    coastalerrormask = gdal.Open(coastalerrormask_raster, gdalconst.GA_ReadOnly)
    coastalerrormaskarray = coastalerrormask.ReadAsArray()
    
    #Create file receiving the ice mask
    #get image size
    rows = coastalerrormask.RasterYSize
    cols = coastalerrormask.RasterXSize   
    
    coastalicemaskraster = numpy.zeros((rows, cols), numpy.float) 
        #Loop through all files to do calculation
    for infile in filelist:
        #Find present data    
        presentyear = int(infile[-22:-18])
        presentmonth = int(infile[-18:-16])
        presentday = int(infile[-16:-14])
        
        presentdate =  datetime.date(presentyear, presentmonth, presentday) 
        
        # ADJUST HOW MANY DAYS PLUS AND MINUS THE PRESENT DATE YOU WANT
        dayrange = 1
        
        #Let ice value in coastal zone persist if there was ice the days around it
        presentdayfilename = outfilepath + "nt_" + presentdate.strftime('%Y%m%d') +  infile[-14:]
        presentdayfile = gdal.Open( presentdayfilename, gdalconst.GA_Update)
        presentdayraster = presentdayfile.ReadAsArray()
        print "Filter consec days for ", presentdayfilename
        
        #Reset coastalicemaskraster to zero
        coastalicemaskraster = numpy.zeros((rows, cols), numpy.float) 
        #Loop through the files around present day and determine how many days there is ice in coastal zone    
        for i in range(-dayrange, dayrange +1):
            diff = datetime.timedelta(days=i)
            diffdate = presentdate + diff
            checkfilename = outfilepath + "nt_" + diffdate.strftime('%Y%m%d') +  infile[-14:]
            
            if os.path.isfile(checkfilename):
                checkfile = gdal.Open(checkfilename, gdalconst.GA_ReadOnly)
                #Read input raster into array
                checkfileraster = checkfile.ReadAsArray()
                
                coastalicemaskraster = numpy.where(  ((checkfileraster >= 38) & (presentdayraster >= 38)), coastalicemaskraster + 1 , coastalicemaskraster )
                
            else:
                #If previous day files do not exist, take present day one -- otherwise it does not add up with number of Days                
                coastalicemaskraster = numpy.where(  (presentdayraster >= 38), coastalicemaskraster + 1 , coastalicemaskraster )
                
                
                
                
        

        
        #Pixel is ice only if presentday is ice (see for loop) AND if a day before OR after is ice (from three days, two need to be ice)
        #This does not shorten or lengthen the ice season since only day before or after is needed
        presentdayraster = numpy.where( (coastalicemaskraster <= ((dayrange * 2)) ), 0, presentdayraster)
        #outarray contains now NumberOfDay with ice -- burn in landmask
        landmask = gdal.Open(landmask_raster, gdalconst.GA_ReadOnly)
        landraster = landmask.ReadAsArray()

        presentdayraster = CopyNonIceValues(landraster, presendayraster)
        
        presentdayfileband = presentdayfile.GetRasterBand(1)
            
        presentdayfileband.WriteArray(presentdayraster)
        presentdayfileband.FlushCache()
    
    
    
        
        
                
        
    
    
        
     
##############################################################################

###   Core of Program follows here ###

##############################################################################


#infilepath = 'U:\\SSMI\\IceConcentration\\NASATEAM\\final-gsfc\\north\\daily\\2012\\'
### Location of needed Raster Masks ###

landmask_raster = 'C:\\Users\\max\\Documents\\IcePersistency\\landmasks\\NSIDC_landmask_raster.tif'
coastalerrormask_raster = "C:\\Users\\max\\Documents\\IcePersistency\\landmasks\\NSIDC_coastalerrormask_raster.tif"
oceanmask_buffer5 = 'C:\Users\max\Documents\IcePersistency\landmasks\NSIDC_oceanmask_buffer5.shp'
NSIDC_balticmask = 'C:\Users\max\Documents\IcePersistency\landmasks\NSIDC_balticmask.tif'


#filelist = glob.glob(infilepath + 'nt_201202*.bin')

#Get all files from given month
startyear = 1985
stopyear = 2014
month = 4                            #Values 1 to 12

monthDict={1:'January', 2:'February', 3:'March', 4:'April', 5:'May', 6:'June', 7:'July', 8:'August', 9:'September', 10:'October', 11:'November', 12:'December'}
#outfilepath = 'C:\\Users\\max\\Documents\\IcePersistency\\' + monthDict[month] + '\\'
outfilepath = 'C:\\Users\\max\\Documents\\IcePersistency\\2014_test\\' + monthDict[month] + '\\'

if os.path.exists(outfilepath):
    answer = raw_input(outfilepath + " exists, delete and overwrite folder? [Y]es?")
    if answer.lower().startswith('y'):
        print "Overwriting " + outfilepath        
        shutil.rmtree(outfilepath)
        os.makedirs(outfilepath)
    else:
        print "Ending program"
        sys.exit()
        
elif not os.path.exists(outfilepath):
    os.makedirs(outfilepath)
    
#Create filelist including all files for the given month between startyear and stopyear inclusive
filelist = []
for year in range(startyear, stopyear + 1):
    foldername = 'U:\\SSMI\\IceConcentration\\NASATEAM\\final-gsfc\\north\\daily\\' + str(year) + '\\'
    if month < 10: 
        file_searchstring = 'nt_' + str(year) + '0' + str(month) + '*.bin'
    else:
        file_searchstring = 'nt_' + str(year)  + str(month) + '*.bin'
    
    foldersearchstring = foldername + file_searchstring
    filelist.extend(glob.glob(foldersearchstring))
    

for icechart in filelist:
    #Convert NSIDC files to GeoTiff
    print'convert ', icechart
    Bin2GeoTiff(icechart, outfilepath)




#FilterConsecDays(outfilepath, landmask_raster, coastalerrormask_raster)

FilterCoastalAreas(outfilepath, landmask_raster, coastalerrormask_raster)
    

#Max / Min must be done before persistence, since the latter is filtered with max-map
max_ice, min_ice = CreateMaxMinIce(outfilepath, outfilepath, landmask_raster, coastalerrormask_raster, oceanmask_buffer5, NSIDC_balticmask )

CreateIcePercistanceMap(outfilepath, outfilepath, max_ice, min_ice, landmask_raster)

print 24*'#'
print "Done creating Ice Persistance Map"
print 24*'#'

