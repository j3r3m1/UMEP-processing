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
                       QgsProcessingParameterString,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterExtent,
                       QgsProcessingException,
                       QgsVectorLayer,
                       QgsFeature,
                       QgsGeometry,
                       QgsPointXY,
                       QgsVectorFileWriter,
                       QgsUnitTypes)

from qgis.PyQt.QtGui import QIcon
from osgeo import gdal, osr
from osgeo.gdalconst import *
import os
import numpy as np
import inspect
from pathlib import Path
import sys
from ..util import misc
from ..util.misc import saverasternd
from ..functions.TreeGenerator import makevegdems


class ProcessingTreeGeneratorAlgorithm(QgsProcessingAlgorithm):
    """
    This algorithm is a processing version of TreeGenerator
    """

    INPUT_POINTLAYER = 'INPUT_POINTLAYER'
    TREE_TYPE = 'TREE_TYPE'
    TOT_HEIGHT = 'TOT_HEIGHT'
    TRUNK_HEIGHT = 'TRUNK_HEIGHT'
    DIA = 'DIA'
    INPUT_DSM = 'INPUT_DSM'
    INPUT_DEM = 'INPUT_DEM'
    INPUT_BUILD = 'INPUT_BUILD'
    INPUT_CDSM = 'INPUT_CDSM'
    INPUT_TDSM = 'INPUT_TDSM'

    CDSM_GRID_OUT = 'CDSM_GRID_OUT'
    TDSM_GRID_OUT = 'TDSM_GRID_OUT'

    
    def initAlgorithm(self, config):
        
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_POINTLAYER,
                                                              self.tr('Point vector layer'), 
                                                              [QgsProcessing.TypeVectorPoint], 
                                                              optional=False))
        self.addParameter(QgsProcessingParameterField(self.TREE_TYPE,
                                                      self.tr('Tree type/shape (1=conifer, 2=decidouos)'),
                                                      '', 
                                                      self.INPUT_POINTLAYER, 
                                                      QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.TOT_HEIGHT,
                                                      self.tr('Total height (m)'),
                                                      '', 
                                                      self.INPUT_POINTLAYER, 
                                                      QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.TRUNK_HEIGHT,
                                                      self.tr('Trunk zone height (m)'),
                                                      '', 
                                                      self.INPUT_POINTLAYER, 
                                                      QgsProcessingParameterField.Numeric))        
        self.addParameter(QgsProcessingParameterField(self.DIA,
                                                      self.tr('Diameter (m)'),
                                                      '', 
                                                      self.INPUT_POINTLAYER, 
                                                      QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_BUILD,
            self.tr('Building grid'), '', optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DSM,
            self.tr('Raster DSM (3D objects and ground). Use if building grid is unavailable.'), '', optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM,
            self.tr('Raster DEM (only ground). Use if building grid is unavailable.'), '', optional=True))

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_CDSM,
            self.tr('Merge with existing vegetation Canopy (C)DSM'), '', optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_TDSM,
            self.tr('Merge with existing vegetation Trunk Zone (T)DSM'), '', optional=True))

        self.addParameter(QgsProcessingParameterRasterDestination(self.CDSM_GRID_OUT,
                                                                  self.tr("Output CDSM"),
                                                                  None,
                                                                  optional=False))
        self.addParameter(QgsProcessingParameterRasterDestination(self.TDSM_GRID_OUT,
                                                                  self.tr("Output TDSM"),
                                                                  None,
                                                                  optional=False))

    def processAlgorithm(self, parameters, context, feedback):
        # InputParameters
        inputPointLayer = self.parameterAsVectorLayer(parameters, self.INPUT_POINTLAYER, context)
        ttype_field = self.parameterAsFields(parameters, self.TREE_TYPE, context)
        trunk_field = self.parameterAsFields(parameters, self.TRUNK_HEIGHT, context)
        tot_field = self.parameterAsFields(parameters, self.TOT_HEIGHT, context)
        dia_field = self.parameterAsFields(parameters, self.DIA, context)
        build = self.parameterAsRasterLayer(parameters, self.INPUT_BUILD, context)
        dsm = self.parameterAsRasterLayer(parameters, self.INPUT_DSM, context)
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        cdsm = self.parameterAsRasterLayer(parameters, self.INPUT_CDSM, context)
        tdsm = self.parameterAsRasterLayer(parameters, self.INPUT_TDSM, context)
        outputCDSM = self.parameterAsOutputLayer(parameters, self.CDSM_GRID_OUT, context)
        outputTDSM = self.parameterAsOutputLayer(parameters, self.TDSM_GRID_OUT, context)

        if build:  # Only building 
            dsm = None
            dem = None

            provider = build.dataProvider()
            filePath_build = str(provider.dataSourceUri())
            dataset = gdal.Open(filePath_build)
            build_array = dataset.ReadAsArray().astype(float)

        else:  # Both building ground heights
            build = None
            if dsm is None:
                raise QgsProcessingException("No valid ground and building DSM raster layer is selected")
            if dem is None:
                raise QgsProcessingException("No valid ground DEM raster layer is selected")

            provider = dsm.dataProvider()
            filePath_dsm = str(provider.dataSourceUri())
            provider = dem.dataProvider()
            filePath_dem = str(provider.dataSourceUri())

            dataset = gdal.Open(filePath_dsm)
            dsm_array = dataset.ReadAsArray().astype(float)
            dataset2 = gdal.Open(filePath_dem)
            dem_array = dataset2.ReadAsArray().astype(float)

            if not (dsm_array.shape[0] == dem_array.shape[0]) & (dsm_array.shape[1] == dem_array.shape[1]):
                raise QgsProcessingException("All grids must be of same pixel resolution")

            build_array = dsm_array - dem_array
            build_array[build_array < 2.] = 1.
            build_array[build_array >= 2.] = 0.

        sizey = build_array.shape[0]
        sizex = build_array.shape[1]

        if cdsm:  # vegetation cdsm
            provider = cdsm.dataProvider()
            filePath_cdsm = str(provider.dataSourceUri())

            dataset = gdal.Open(filePath_cdsm)
            cdsm_array = dataset.ReadAsArray().astype(float)
            # tdsm = self.layerComboManagerCDSM.currentLayer()
            if tdsm is None:
                # raise QgsProcessingException("No valid vegetation TDSM raster layer is selected. Both CDSM and TDSM must be selected if merging with existing.")
                feedback.setProgressText("No TDSM raster layer is selected. Creating new TDSM raster layer.")
                tdsm_array = np.zeros((sizey, sizex))
                # return
            else:
                provider = tdsm.dataProvider()
                filePath_tdsm = str(provider.dataSourceUri())

                dataset = gdal.Open(filePath_tdsm)
                tdsm_array = dataset.ReadAsArray().astype(float)

        else:
            cdsm_array = np.zeros((sizey, sizex))
            tdsm_array = np.zeros((sizey, sizex))

        geotransform = dataset.GetGeoTransform()
        scale = 1 / geotransform[1]

        # Check units of raster data. Should be in meters or feet.
        if build:
            crs_temp = build.crs()
            unit_temp = crs_temp.mapUnits()
        else:
            crs_temp = dsm.crs()
            unit_temp = crs_temp.mapUnits()   

        # print(QgsUnitTypes.toString(unit_temp))         
        temp_crs = osr.SpatialReference()
        temp_crs.ImportFromWkt(dataset.GetProjection())
        temp_unit = temp_crs.GetAttrValue('UNIT')
        possible_units = ['metre', 'Metre', 'metres', 'Metres', 'meter', 'Meter', 'meters', 'Meters', 'm', 'ft', 'US survey foot', 'feet', 'Feet', 'foot', 'Foot', 'ftUS', 'International foot'] # Possible units
        if not temp_unit in possible_units:
            raise QgsProcessingException('Error! Raster data is currently in ' + QgsUnitTypes.toString(unit_temp) + '. Meters or feet required. Please reproject.')
            return

        # Get attributes
        vlayer = inputPointLayer
        idx_ttype = vlayer.fields().indexFromName(ttype_field[0])
        idx_trunk = vlayer.fields().indexFromName(trunk_field[0])
        idx_tot = vlayer.fields().indexFromName(tot_field[0])
        idx_dia = vlayer.fields().indexFromName(dia_field[0])

        numfeat = vlayer.featureCount()
        width = dataset.RasterXSize
        height = dataset.RasterYSize
        minx = geotransform[0]
        miny = geotransform[3] + width * geotransform[4] + height * geotransform[5]
        rows = build_array.shape[0]
        cols = build_array.shape[1]

        # Check CRS of raster and vector layers. Needs to be the same.
        if build:
            if cdsm:
                if not ((build.crs().authid() == vlayer.crs().authid()) & (build.crs().authid() == cdsm.crs().authid())):
                    raise QgsProcessingException("Error! Check the coordinate systems of your input data. Have to match!")
                    return
            else:
                if not (build.crs().authid() == vlayer.crs().authid()):
                    raise QgsProcessingException("Error! Check the coordinate systems of your input data. Have to match!")
                    return
        else:
            if cdsm:
                if not ((dsm.crs().authid() == vlayer.crs().authid()) & (dsm.crs().authid() == cdsm.crs().authid())):
                    raise QgsProcessingException("Error! Check the coordinate systems of your input data. Have to match!")
                    return
            else:
                if not (dsm.crs().authid() == vlayer.crs().authid()):
                    raise QgsProcessingException("Error! Check the coordinate systems of your input data. Have to match!")
                    return

        index = 1
        # Main loop
        for f in vlayer.getFeatures():  # looping through each grid polygon

            feedback.setProgress(int((index * 100) / numfeat))
            if feedback.isCanceled():
                feedback.setProgressText("Calculation cancelled")
                break
            index = index + 1

            attributes = f.attributes()
            geometry = f.geometry()
            feature = QgsFeature()
            feature.setAttributes(attributes)
            feature.setGeometry(geometry)

            y = f.geometry().centroid().asPoint().y()
            x = f.geometry().centroid().asPoint().x()
            ttype = f.attributes()[idx_ttype]
            trunk = f.attributes()[idx_trunk]
            height = f.attributes()[idx_tot]
            dia = f.attributes()[idx_dia]
            cola = np.round((x - minx) * scale)
            rowa = np.round((miny + rows / scale - y) * scale)

            # feedback.setProgressText("scale= " + str(scale))
            # feedback.setProgressText("x= " + str(x))
            # feedback.setProgressText("y= " + str(y))
            # feedback.setProgressText("minx= " + str(minx))
            # feedback.setProgressText("miny= " + str(miny))
            # feedback.setProgressText("cola= " + str(cola))
            # feedback.setProgressText("rowa= " + str(rowa))
            # feedback.setProgressText("rows= " + str(rows))

            # Check if there are trees with a tree canopy diameter smaller than the pixel resolution of the input raster data
            if dia < geotransform[1]:
                raise QgsProcessingException("Error! You have tree canopy diameters that are smaller than the pixel resolution.")

            cdsm_array, tdsm_array = makevegdems.vegunitsgeneration(build_array, cdsm_array, tdsm_array, ttype, height,
                                                                    trunk, dia, rowa, cola, sizex, sizey, scale)

        saverasternd(dataset, outputCDSM, cdsm_array)
        saverasternd(dataset, outputTDSM, tdsm_array)

        feedback.setProgressText("Processing finished.")

        return {self.CDSM_GRID_OUT: outputCDSM, self.TDSM_GRID_OUT: outputTDSM}
    
    def name(self):
        return 'Spatial Data: Tree Generator'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Pre-Processor'

    def shortHelpString(self):
        return self.tr('Information 3d vegetation is not a common spatial information available. '
                       'The Tree Generator can be used to create or alter a raster-ased vegetation Canopy '
                       'Digital Surface Model (CDSM) and Trunk Zone (T)DSM (see Help for abbreviations). '
                       'Information from a point layer where the location of the points specifies the tree '
                       'positions and the attributes sets the shape of the trees, is used to produce '
                       'a 3d vegetation raster needed for e.g. Mean radiant temperature modelling (SOLWEIG) '
                       'or Urban Energy Balance modelling (SUEWS) in UMEP.\n'
                       '---------------\n'
                       'Full manual available via the <b>Help</b>-button.')
    
    def helpUrl(self):
        url = "https://umep-docs.readthedocs.io/en/latest/pre-processor/Spatial%20Data%20Tree%20Generator.html"
        return url

    def tr(self, string):
        return QCoreApplication.translate('Pre-Processing', string)

    def icon(self):
        cmd_folder = Path(os.path.split(inspect.getfile(inspect.currentframe()))[0]).parent
        icon = QIcon(str(cmd_folder) + "/icons/icon_tree.png")
        return icon

    def createInstance(self):
        return ProcessingTreeGeneratorAlgorithm()