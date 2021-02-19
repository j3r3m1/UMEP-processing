# -*- coding: utf-8 -*-

"""
/***************************************************************************
 ProcessingUMEP
                                 A QGIS plugin
 UMEP for processing toolbox
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-04-02
        copyright            : (C) 2020 by Fredrik Lindberg
        email                : fredrikl@gvc.gu.se
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Fredrik Lindberg'
__date__ = '2020-04-02'
__copyright__ = '(C) 2020 by Fredrik Lindberg'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                    #    QgsProcessingParameterString,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterNumber,
                    #    QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                    #    QgsProcessingParameterField,
                       QgsProcessingException,
                       QgsVectorLayer,
                       QgsFeature,
                       QgsVectorFileWriter,
                       QgsVectorDataProvider,
                       QgsField,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterDefinition)
from qgis.PyQt.QtGui import QIcon
from osgeo import gdal, osr, ogr
from osgeo.gdalconst import *
import os
import numpy as np
import inspect
from pathlib import Path
import sys
from ..util import misc
# from ..util import RoughnessCalcFunctionV2 as rg
# from ..util import imageMorphometricParms_v1 as morph

# Modules necessary for Tree Planter
#import numpy as np
#from osgeo import gdal, osr, ogr
import matplotlib.pylab as plt
#import os
import time
import math
import glob
import datetime
import scipy as sp
from scipy.ndimage import label

# Import UMEP tools
from ..util.SEBESOLWEIGCommonFiles.Solweig_v2015_metdata_noload import Solweig_2015a_metdata_noload
# from ..util.SEBESOLWEIGCommonFiles import Solweig_v2015_metdata_noload as metload
from ..util.SEBESOLWEIGCommonFiles.clearnessindex_2013b import clearnessindex_2013b

from ..functions.TreeGenerator import makevegdems as makevegdems

# from ..functions.TreePlanter.SOLWEIG.shadowingfunction_wallheight_23 import shadowingfunction_wallheight_23
from ..util.SEBESOLWEIGCommonFiles.shadowingfunction_wallheight_23 import shadowingfunction_wallheight_23
from ..functions.TreePlanter.SOLWEIG1D import Solweig1D_2019a_calc as so
from ..functions.wallalgorithms import findwalls
# from ..functions.TreePlanter.SOLWEIG.misc import saveraster
from ..util.misc import saveraster

# Import functions and classes for Tree planter
from ..functions.TreePlanter.TreePlanter import TreePlanterPrepare
from ..functions.TreePlanter.TreePlanter import TreePlanterHillClimber
from ..functions.TreePlanter.TreePlanter.TreePlanterClasses import Inputdata, Treedata, Regional_groups, ClippedInputdata, Treerasters
from ..functions.TreePlanter.TreePlanter import GreedyAlgorithm
from ..functions.TreePlanter.SOLWEIG1D.SOLWEIG_1D import tmrt_1d_fun
# from ..functions.TreePlanter.treeplanterclasses import Treedata
# from ..functions.TreePlanter.treeplanterclasses import Regional_groups
# from ..functions.TreePlanter.treeplanterclasses import ClippedInputdata
# from ..functions.TreePlanter.treeplanterclasses import Treerasters

class ProcessingTreePlanterAlgorithm(QgsProcessingAlgorithm):
    """
    This algorithm is a processing version of Tree planter
    """

    TTYPE = 'TTYPE'
    HEIGHT = 'HEIGHT'
    DIA = 'DIA'
    TRUNK = 'TRUNK'
    TRANS_VEG = 'TRANS_VEG'
    INPUT_POLYGONLAYER = 'INPUT_POLYGONLAYER'
    NTREE = 'NTREE'
    SOLWEIG_DIR = 'SOLWEIG_DIR'
    #INPUT_MET = 'INPUT_MET'
    START_HOUR = 'START_HOUR'
    END_HOUR = 'END_HOUR'

    # Advanced
    ITERATIONS = 'ITERATIONS'
    INCLUDE_OUTSIDE = 'INCLUDE_OUTSIDE'
    RANDOM_STARTING = 'RANDOM_STARTING'
    GREEDY_ALGORITHM = 'GREEDY_ALGORITHM'

    # Output
    OUTPUT_CDSM = 'OUTPUT_CDSM'
    OUTPUT_POINTFILE = 'OUTPUT_POINTFILE'
    OUTPUT_TMRT = 'OUTPUT_TMRT'

    def initAlgorithm(self, config):

        self.addParameter(QgsProcessingParameterFile(self.SOLWEIG_DIR,
            'Path to SOLWEIG output directory', QgsProcessingParameterFile.Folder))
        #self.addParameter(QgsProcessingParameterFile(self.INPUT_MET,
        #    self.tr('Input meteorological file'), extension='txt'))
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_POLYGONLAYER,
           self.tr('Planting area (Vector polygon)'), [QgsProcessing.TypeVectorPolygon]))
        # self.addParameter(QgsProcessingParameterFile(self.INPUT_POLYGONLAYER,
        #     self.tr('Planting area (Vector polygon)'), extension='shp'))
        ttype = ((self.tr('Deciduous'), '0'),
                        (self.tr('Conifer'), '1'))
        self.addParameter(QgsProcessingParameterNumber(self.START_HOUR,
            self.tr('From (hour)'),
            QgsProcessingParameterNumber.Integer,
            QVariant(13), False, minValue=0, maxValue=23))
        self.addParameter(QgsProcessingParameterNumber(self.END_HOUR,
            self.tr('Thru (hour)'),
            QgsProcessingParameterNumber.Integer,
            QVariant(15), False, minValue=0, maxValue=23))
        self.addParameter(QgsProcessingParameterEnum(self.TTYPE,
            self.tr('Tree type'),
            options=[i[0] for i in ttype], defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.HEIGHT, 
            self.tr('Tree height (meter above ground level)'),
            QgsProcessingParameterNumber.Double,
            QVariant(10), False, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.DIA, 
            self.tr('Tree canopy diameter (meter)'),
            QgsProcessingParameterNumber.Double,
            QVariant(5), False, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.TRUNK, 
            self.tr('Trunk zone height (meter above ground level)'),
            QgsProcessingParameterNumber.Double,
            QVariant(3), False, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.TRANS_VEG,
            self.tr('Transmissivity of light through vegetation (%)'),
            QgsProcessingParameterNumber.Integer,
            QVariant(3), False, minValue=0, maxValue=100))
        self.addParameter(QgsProcessingParameterNumber(self.NTREE, 
            self.tr('Number of trees to plant'),
            QgsProcessingParameterNumber.Integer,
            QVariant(3), False, minValue=1))
        
        # Output
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_CDSM,
            self.tr("Canopy Digital Surface Model"),
            None, False))

        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT_POINTFILE,
            self.tr("Vector point file with tree location(s)")
            )
        )

        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_TMRT,
            self.tr("Mean Tmrt of timesteps studied"),
            None, False))

        # Advanced parameters
        iterations = QgsProcessingParameterNumber(self.ITERATIONS,
            self.tr("Number of restart iterations"), 
            QgsProcessingParameterNumber.Integer, defaultValue=2000, minValue=1)
        iterations.setFlags(iterations.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(iterations)
        
        includeOutside = QgsProcessingParameterBoolean(self.INCLUDE_OUTSIDE,
            self.tr("Allow areas outside of Planting area to be included in calculation"), defaultValue=True)
        includeOutside.setFlags(includeOutside.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(includeOutside)
        
        randomStarting = QgsProcessingParameterBoolean(self.RANDOM_STARTING, 
            self.tr("Use random starting positions in the hill climbing algorithm"), defaultValue=False)
        randomStarting.setFlags(randomStarting.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(randomStarting)       

        greedyAlgorithm = QgsProcessingParameterBoolean(self.GREEDY_ALGORITHM, 
            self.tr("Use a greedy algorithm to position trees"), defaultValue=False)
        greedyAlgorithm.setFlags(greedyAlgorithm.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(greedyAlgorithm)

    def processAlgorithm(self, parameters, context, feedback):
        # InputParameters 

        # SOLWEIG_DIR = 'SOLWEIG_DIR'
        # OUTPUT_DIR = 'OUTPUT_DIR'
        # ITERATIONS = 'ITERATIONS'
        # INCLUDE_OUTSIDE = 'INCLUDE_OUTSIDE'
        # INPUT_MET = 'INPUT_MET'
        # START_HOUR = 'START_HOUR'
        # END_HOUR = 'END_HOUR'

        infolder = self.parameterAsString(parameters, self.SOLWEIG_DIR, context)
        ttype = self.parameterAsString(parameters, self.TTYPE, context)
        height = self.parameterAsDouble(parameters, self.HEIGHT, context)
        dia = self.parameterAsDouble(parameters, self.DIA, context)
        trunk = self.parameterAsDouble(parameters, self.TRUNK, context)
        transVeg = self.parameterAsDouble(parameters, self.TRANS_VEG, context)
        nTree = self.parameterAsInt(parameters, self.NTREE, context)
        transVeg = (self.parameterAsDouble(parameters, self.TRANS_VEG, context) / 100)
        #INPUT_MET = self.parameterAsString(parameters, self.INPUT_MET, context)
        INPUT_MET = infolder + '/metfile.txt'
        ITERATIONS = self.parameterAsInt(parameters, self.ITERATIONS, context)
        h_start = self.parameterAsString(parameters, self.START_HOUR, context)
        h_end = self.parameterAsString(parameters, self.END_HOUR, context)

        outside_selected = self.parameterAsBoolean(parameters, self.INCLUDE_OUTSIDE, context)
        greedy = self.parameterAsBoolean(parameters, self.GREEDY_ALGORITHM, context)
        starting_algorithm = self.parameterAsBoolean(parameters, self.RANDOM_STARTING, context)

        # inputPolygonlayer = parameters[self.INPUT_POLYGONLAYER]
        inputPolygonlayer = self.parameterAsVectorLayer(parameters, self.INPUT_POLYGONLAYER, context).dataProvider().dataSourceUri()

        outputCDSM = self.parameterAsOutputLayer(parameters, self.OUTPUT_CDSM, context)
        outputPoint = self.parameterAsOutputLayer(parameters, self.OUTPUT_POINTFILE, context)
        outputTMRT = self.parameterAsOutputLayer(parameters, self.OUTPUT_TMRT, context)

        feedback.setProgressText("Initializing and loading layers...")

        # TREE PLANTER CODE

        h_start = h_start + '00'
        h_end = h_end + '00'

        ## List shadow and tmrt files in infolder
        sh_fl = [f for f in glob.glob(infolder + '/Shadow_*.tif')]
        tmrt_fl = [f for f in glob.glob(infolder + '/Tmrt_*.tif')]

        # Creating vector with hours from file names
        h_fl = np.zeros((sh_fl.__len__(),1))
        for iz in range(sh_fl.__len__()):
            h_fl[iz,0] = np.float(sh_fl[iz][-9:-5])

        for ix in range(sh_fl.__len__()):
            if h_start in sh_fl[ix]:
                r1 = ix
                break

        for iy in range(sh_fl.__len__()):
            if h_end in sh_fl[iy]:
                r2 = iy
                break

        r_range = range(r1,r2)

        # Loading all shadow and tmrt rasters and summing up all tmrt into one
        tree_input = Inputdata(r_range, sh_fl, tmrt_fl, infolder, inputPolygonlayer)

        if not outside_selected:
            feedback.setProgressText("Tree shade ineffective outside planting area...")
            tree_input.buildings = tree_input.buildings * tree_input.selected_area
            for i in np.arange(tree_input.tmrt_ts.shape[2]):
                tree_input.tmrt_ts[:,:,i] = tree_input.tmrt_ts[:,:,i] * tree_input.selected_area
                tree_input.shadow[:,:,i] = tree_input.shadow[:,:,i] * tree_input.selected_area

        # Tmrt for shaded point
        tmrt_1d, azimuth, altitude, amaxvalue = tmrt_1d_fun(INPUT_MET,infolder,transVeg,tree_input.lon,tree_input.lat,tree_input.dsm,r_range)
        tmrt_1d = np.around(tmrt_1d, decimals=1) # Round Tmrt to one decimal

        # Create tree in empty matrix
        treey = math.ceil(tree_input.rows / 2)  # Y-position of tree in empty setting. Y-position is in the middle of Y.
        treex = math.ceil(tree_input.cols / 2)  # X-position of tree in empty setting. X-position is in the middle of X.

        # Create Treedata class object
        treedata = Treedata(ttype, height, trunk, dia, treey, treex)

        # Copy of building raster
        bld_orig = tree_input.buildings.copy()

        # Remove all Tmrt values that are on top of buildings
        tree_input.tmrt_s = tree_input.tmrt_s * tree_input.buildings  

        cdsm_ = np.zeros((tree_input.rows, tree_input.cols))  # Empty cdsm
        tdsm_ = np.zeros((tree_input.rows, tree_input.cols))  # Empty tdsm
        dsm_empty = np.ones((tree_input.rows, tree_input.cols))  # Empty dsm raster
        buildings_empty = np.ones((tree_input.rows, tree_input.cols))  # Empty building raster

        rowcol = tree_input.rows*tree_input.cols

        # CDSM and TDSM for new tree
        cdsm_, tdsm_ = makevegdems.vegunitsgeneration(buildings_empty, cdsm_, tdsm_, treedata.ttype, treedata.height, treedata.trunk, treedata.dia, treedata.treey, treedata.treex,
                                               tree_input.cols, tree_input.rows, tree_input.scale)

        # Create shadows for new tree
        treebush = np.zeros((tree_input.rows, tree_input.cols))  # Empty tree bush matrix

        treewalls = np.zeros((tree_input.rows, tree_input.cols))  # Empty tree walls matrix
        treewallsdir = np.zeros((tree_input.rows, tree_input.cols))  # Empty tree walls direction matrix

        treesh_ts1 = np.zeros((tree_input.rows, tree_input.cols, r_range.__len__()))      # Shade for each timestep, shade = 0
        treesh_ts2 = np.zeros((tree_input.rows, tree_input.cols, r_range.__len__()))      # Shade for each timestep, shade = 1
        treesh_sum_sh = np.zeros((tree_input.rows,tree_input.cols))                       # Sum of shade for all timesteps
        treesh_sum_tmrt = np.zeros((tree_input.rows, tree_input.cols))                    # Sum of tmrt for all timesteps

        dem_temp = np.ones((tree_input.rows,tree_input.cols))

        # Create shadow for new tree
        i_c = 0
        for i in r_range:
            vegsh, sh, _, wallsh, wallsun, wallshve, _, facesun = shadowingfunction_wallheight_23(dem_temp, cdsm_, tdsm_,
                                                                                                azimuth[0][i], altitude[0][i], tree_input.scale,
                                                                                                amaxvalue, treebush, treewalls,
                                                                                                treewallsdir * np.pi / 180.)

            treesh_ts1[:, :, i_c] = vegsh
            treesh_ts2[:, :, i_c] = (1 - vegsh)
            treesh_sum_sh = treesh_sum_sh + treesh_ts2[:,:,i_c] * i
            treesh_sum_tmrt[:, :] = treesh_sum_tmrt + treesh_ts2[:,:,i_c] * tmrt_1d[i_c,0]
            i_c += 1

        ## Regional groups for tree shadows
        shadow_rg = Regional_groups(r_range, treesh_sum_sh, treesh_ts2, tmrt_1d)

        # Create rasters for new tree; shadows and Tmrt
        treerasters = Treerasters(treesh_sum_tmrt, shadow_rg.shadow, treesh_ts1, cdsm_, treedata)

        # Crop to size of inputPolygonlayer
        cropped_rasters = ClippedInputdata(tree_input, treerasters)

        if greedy:
            # Greedy algorithm
            feedback.setProgressText("Running with greedy algorithm...")
            t_y, t_x = GreedyAlgorithm.greedyplanter(cropped_rasters, treedata, treerasters, tmrt_1d, nTree, feedback)
        else:
            # Hill climbing algorithm
            # Creating matrices with Tmrt for tree shadows at each possible position
            treerasters, positions = TreePlanterPrepare.treeplanter(cropped_rasters, treedata, treerasters, tmrt_1d)

            # Starting algorithm.
            if starting_algorithm:
                sa = 0
                feedback.setProgressText("Running hill climbing algorithm with random algorithm for starting positions...")
            else:
                sa = 1
                feedback.setProgressText("Running hill climbing algorithm with genetic algorithm for starting positions...")

            if nTree == 1:
                t_y, t_x = np.where(treerasters.d_tmrt == np.max(treerasters.d_tmrt))
            else:
                possible_locations = np.sum(treerasters.d_tmrt > 0)
                feedback.setProgressText(str(possible_locations) + " possible locations for trees...")
                # Running tree planter
                t_y, t_x = TreePlanterHillClimber.treeoptinit(treerasters, cropped_rasters, positions, treedata,
                                                                                                    shadow_rg, tmrt_1d, nTree, ITERATIONS, sa, feedback)

        t_y = t_y + cropped_rasters.clip_rows[0]
        t_x = t_x + cropped_rasters.clip_cols[0]

        cdsm_tmrt = np.zeros((tree_input.rows, tree_input.cols, nTree))
        tdsm_tmrt = np.zeros((tree_input.rows, tree_input.cols, nTree))

        cdsm_new = np.zeros((tree_input.rows,tree_input.cols))
        tdsm_new = np.zeros((tree_input.rows,tree_input.cols))

        for i in range(0,nTree):
            cdsm_ = np.zeros((tree_input.rows,tree_input.cols))       # Empty cdsm
            tdsm_ = np.zeros((tree_input.rows,tree_input.cols))       # Empty tdsm

            cdsm_tmrt[:,:,i], tdsm_tmrt[:,:,i] = makevegdems.vegunitsgeneration(bld_orig, cdsm_, tdsm_, 
                                                                treedata.ttype, treedata.height, treedata.trunk, treedata.dia, 
                                                                t_y[i], t_x[i], 
                                                                tree_input.cols, tree_input.rows, tree_input.scale)

            cdsm_new = cdsm_new + cdsm_tmrt[:, :, i]
            tdsm_new = tdsm_new + tdsm_tmrt[:, :, i]

        cdsm_new = cdsm_new + tree_input.cdsm
        # Save CDSM as raster
        saveraster(tree_input.dataSet, outputCDSM, cdsm_new)

        # Save Tmrt raster
        saveraster(tree_input.dataSet, outputTMRT, tree_input.tmrt_avg)

        # Create point vector and save as shapefile
        srs = osr.SpatialReference()
        srs.ImportFromWkt(tree_input.dataSet.GetProjection())
        driver = ogr.GetDriverByName('ESRI Shapefile')
        shapeFile = driver.CreateDataSource(outputPoint)

        shapeLayer = shapeFile.CreateLayer('ogr_pts', srs, ogr.wkbPoint)
        layerDefinition = shapeLayer.GetLayerDefn()

        # Add fields for tree height, canopy diameter and trunk height
        FIDField = ogr.FieldDefn("FID", ogr.OFTInteger)
        shapeLayer.CreateField(FIDField)
        heightField = ogr.FieldDefn("height", ogr.OFTReal)
        heightField.SetWidth(5)
        heightField.SetPrecision(2)
        shapeLayer.CreateField(heightField)
        diameterField = ogr.FieldDefn("diameter", ogr.OFTReal)
        diameterField.SetWidth(5)
        diameterField.SetPrecision(2)
        shapeLayer.CreateField(diameterField)
        trunkField = ogr.FieldDefn("trunk", ogr.OFTReal)
        trunkField.SetWidth(5)
        trunkField.SetPrecision(2)
        shapeLayer.CreateField(trunkField)

        (minx, x_size, x_rotation, miny, y_rotation, y_size) = tree_input.dataSet.GetGeoTransform()
        for i in range(0,nTree):
            temp_y = t_y[i] * y_size + miny + (y_size / 2)
            #temp_y = t_y[i] * y_size + miny # + (1 / y_size)
            temp_x = t_x[i] * x_size + minx + (x_size / 2)
            #temp_x = t_x[i] * x_size + minx # + (1 / x_size)
            
            point = ogr.Geometry(ogr.wkbPoint)
            point.SetPoint(0, temp_x, temp_y)

            feature = ogr.Feature(layerDefinition)
            feature.SetGeometry(point)
            feature.SetFID(i)
            feature.SetField("FID", i)
            feature.SetField("height", treedata.height)
            feature.SetField("diameter", treedata.dia)
            feature.SetField("trunk", treedata.trunk)

            shapeLayer.CreateFeature(feature)

            feature = None

        shapeFile.Destroy()

        feedback.setProgressText("TreePlanter: Model calculation finished.")

        return {self.OUTPUT_CDSM: outputCDSM, self.OUTPUT_POINTFILE: outputPoint}
    
    def name(self):
        return 'Outdoor Thermal Comfort: TreePlanter'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Processor'

    def shortHelpString(self):
        return self.tr('This is a model for optimization of tree arrangement to mitigate thermal ' 
        'heat stress with respect to radiant load represented by mean radiant temperature (Tmrt). '
        'The optimization of tree arrangement is achieved by utilizing '
        'a metaheuristic hill-climbing algorithm that evaluates the combined shading effect of 1 to N '
        'trees and their corresponding mitigating decrease in Tmrt.\n'
        '\n'
        '<b>Default settings:</b>'
        '<ul><li>Metaheuristic algorithm = Hill-climbing algorithm</li>'
        '<li>Algorithm for starting positions = genetic</li>'
        '<li>Number of iterations = 2000</li>'
        '<li>Areas outside of Planting area are included</li></ul>'
        '\n'
        '<b>TIPS and TRICKS for best performance:</b><br>'
        '- The input folder (Path to SOLWEIG output directory) should have been produced beforehand using the SOLWEIG-' 
        'model with the option to "Save necessary rasters for the TreePlanter tool" ticked in\n' 
        '- The model has a very high computational complexity. Therefore, try to reduce the number of variables by e.g.: \n'
        '   + Use a low number of trees\n' 
        '   + Try to use small area as planting area\n'
        '   + Use hourly meteorological data, preferably one single day.\n'
        '   If running with a large number of trees, or over a large extent, consider using the greedy algorithm.\n'
        '-------------\n'
        'Wallenberg and Lindberg (2020): Geoscientific Model Development, in review<br>'
        '--------------\n'
        'Full manual available via the <b>Help</b>-button.')

    def helpUrl(self):
        url = "https://umep-docs.readthedocs.io/en/latest/processor/Outdoor%20Thermal%20Comfort%20TreePlanter.html"
        return url

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def icon(self):
        cmd_folder = Path(os.path.split(inspect.getfile(inspect.currentframe()))[0]).parent
        icon = QIcon(str(cmd_folder) + "/icons/icon_tree.png")
        return icon

    def createInstance(self):
        return ProcessingTreePlanterAlgorithm()
