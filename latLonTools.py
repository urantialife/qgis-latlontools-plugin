from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QApplication, QToolButton
from qgis.core import Qgis, QgsCoordinateTransform, QgsVectorLayer, QgsRectangle, QgsPoint, QgsPointXY, QgsGeometry, QgsWkbTypes, QgsProject, QgsApplication
from qgis.gui import QgsRubberBand
import processing

from .latLonFunctions import InitLatLonFunctions, UnloadLatLonFunctions
from .zoomToLatLon import ZoomToLatLon
from .multizoom import MultiZoomWidget
from .settings import SettingsWidget, settings
from .provider import LatLonToolsProvider
from .util import epsg4326
from .captureExtent import getExtentString
import os


class LatLonTools:
    digitizerDialog = None
    convertCoordinateDialog = None
    mapTool = None
    showMapTool = None
    copyExtentTool = None

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.crossRb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.crossRb.setColor(Qt.red)
        self.provider = LatLonToolsProvider()
        self.toolbar = self.iface.addToolBar('Lat Lon Tools Toolbar')
        self.toolbar.setObjectName('LatLonToolsToolbar')

    def initGui(self):
        '''Initialize Lot Lon Tools GUI.'''
        # Initialize the Settings Dialog box
        self.settingsDialog = SettingsWidget(self, self.iface, self.iface.mainWindow())

        # Add Interface for Coordinate Capturing
        icon = QIcon(os.path.dirname(__file__) + "/images/copyicon.svg")
        self.copyAction = QAction(icon, "Copy/Display Coordinate", self.iface.mainWindow())
        self.copyAction.setObjectName('latLonToolsCopy')
        self.copyAction.triggered.connect(self.startCapture)
        self.copyAction.setCheckable(True)
        self.toolbar.addAction(self.copyAction)
        self.iface.addPluginToMenu("Lat Lon Tools", self.copyAction)

        # Add Interface for External Map
        icon = QIcon(os.path.dirname(__file__) + "/images/mapicon.png")
        self.externMapAction = QAction(icon, "Show in External Map", self.iface.mainWindow())
        self.externMapAction.setObjectName('latLonToolsExternalMap')
        self.externMapAction.triggered.connect(self.setShowMapTool)
        self.externMapAction.setCheckable(True)
        self.toolbar.addAction(self.externMapAction)
        self.iface.addPluginToMenu("Lat Lon Tools", self.externMapAction)

        # Add Interface for Zoom to Coordinate
        icon = QIcon(os.path.dirname(__file__) + "/images/zoomicon.svg")
        self.zoomToAction = QAction(icon, "Zoom To Coordinate", self.iface.mainWindow())
        self.zoomToAction.setObjectName('latLonToolsZoom')
        self.zoomToAction.triggered.connect(self.showZoomToDialog)
        self.toolbar.addAction(self.zoomToAction)
        self.iface.addPluginToMenu('Lat Lon Tools', self.zoomToAction)

        self.zoomToDialog = ZoomToLatLon(self, self.iface, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.zoomToDialog)
        self.zoomToDialog.hide()

        # Add Interface for Multi point zoom
        icon = QIcon(os.path.dirname(__file__) + '/images/multizoom.svg')
        self.multiZoomToAction = QAction(icon, "Multi-location Zoom", self.iface.mainWindow())
        self.multiZoomToAction.setObjectName('latLonToolsMultiZoom')
        self.multiZoomToAction.triggered.connect(self.multiZoomTo)
        self.toolbar.addAction(self.multiZoomToAction)
        self.iface.addPluginToMenu('Lat Lon Tools', self.multiZoomToAction)

        self.multiZoomDialog = MultiZoomWidget(self, self.settingsDialog, self.iface.mainWindow())
        self.multiZoomDialog.hide()
        self.multiZoomDialog.setFloating(True)

        menu = QMenu()
        # Add Interface for copying the canvas extent
        icon = QIcon(os.path.dirname(__file__) + "/images/copycanvas.svg")
        self.copyCanvasAction = menu.addAction(icon, 'Copy Canvas Extent', self.copyCanvas)
        self.copyCanvasAction.setObjectName('latLonToolsCopyCanvasExtent')
        # Add Interface for copying an interactive extent
        icon = QIcon(os.path.dirname(__file__) + "/images/copyextent.svg")
        self.copyExtentAction = menu.addAction(icon, 'Copy Selected Area Extent', self.copyExtent)
        self.copyExtentAction.setCheckable(True)
        self.copyExtentAction.setObjectName('latLonToolsCopySelectedAreaExtent')
        # Add Interface for copying a layer extent
        icon = QIcon(os.path.dirname(__file__) + "/images/copylayerextent.svg")
        self.copyLayerExtentAction = menu.addAction(icon, 'Copy Layer Extent', self.copyLayerExtent)
        self.copyLayerExtentAction.setObjectName('latLonToolsCopyLayerExtent')
        # Add Interface for copying the extent of selected features
        icon = QIcon(os.path.dirname(__file__) + "/images/copyselectedlayerextent.svg")
        self.copySelectedFeaturesExtentAction = menu.addAction(icon, 'Copy Selected Features Extent', self.copySelectedFeaturesExtent)
        self.copySelectedFeaturesExtentAction.setObjectName('latLonToolsCopySelectedFeaturesExtent')
        
        # Add the copy extent tools to the menu
        icon = QIcon(os.path.dirname(__file__) + '/images/copylayerextent.svg')
        self.copyExtentsAction = QAction(icon, 'Copy Extents to Clipboard', self.iface.mainWindow())
        self.copyExtentsAction.setMenu(menu)
        self.iface.addPluginToMenu('Lat Lon Tools', self.copyExtentsAction)

        # Add the copy extent tools to the toolbar
        self.copyExtentButton = QToolButton()
        self.copyExtentButton.setMenu(menu)
        self.copyExtentButton.setDefaultAction(self.copyCanvasAction)
        self.copyExtentButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.copyExtentButton.triggered.connect(self.copyExtentTriggered)
        self.copyExtentToolbar = self.toolbar.addWidget(self.copyExtentButton)

        # Create the coordinate converter menu
        icon = QIcon(':/images/themes/default/mIconProjectionEnabled.svg')
        self.convertCoordinatesAction = QAction(icon, "Coordinate Conversion", self.iface.mainWindow())
        self.convertCoordinatesAction.setObjectName('latLonToolsCoordinateConversion')
        self.convertCoordinatesAction.triggered.connect(self.convertCoordinatesTool)
        self.toolbar.addAction(self.convertCoordinatesAction)
        self.iface.addPluginToMenu("Lat Lon Tools", self.convertCoordinatesAction)

        # Create the conversions menu
        menu = QMenu()
        icon = QIcon(os.path.dirname(__file__) + '/images/field2geom.svg')
        action = menu.addAction(icon, "Fields to point layer", self.field2geom)
        action.setObjectName('latLonToolsField2Geom')
        icon = QIcon(os.path.dirname(__file__) + '/images/geom2field.svg')
        action = menu.addAction(icon, "Point layer to fields", self.geom2Field)
        action.setObjectName('latLonToolsGeom2Field')
        icon = QIcon(os.path.dirname(__file__) + '/images/pluscodes.svg')
        action = menu.addAction(icon, "Plus Codes to point layer", self.PlusCodestoLayer)
        action.setObjectName('latLonToolsPlusCodes2Geom')
        action = menu.addAction(icon, "Point layer to Plus Codes", self.toPlusCodes)
        action.setObjectName('latLonToolsGeom2PlusCodes')
        icon = QIcon(os.path.dirname(__file__) + '/images/mgrs2point.svg')
        action = menu.addAction(icon, "MGRS to point layer", self.MGRStoLayer)
        action.setObjectName('latLonToolsMGRS2Geom')
        icon = QIcon(os.path.dirname(__file__) + '/images/point2mgrs.svg')
        action = menu.addAction(icon, "Point layer to MGRS", self.toMGRS)
        action.setObjectName('latLonToolsGeom2MGRS')
        self.conversionsAction = QAction(icon, "Conversions", self.iface.mainWindow())
        self.conversionsAction.setMenu(menu)
        self.iface.addPluginToMenu('Lat Lon Tools', self.conversionsAction)

        # Add to Digitize Toolbar
        icon = QIcon(os.path.dirname(__file__) + '/images/latLonDigitize.svg')
        self.digitizeAction = QAction(icon, "Lat Lon Digitize", self.iface.mainWindow())
        self.digitizeAction.setObjectName('latLonToolsDigitize')
        self.digitizeAction.triggered.connect(self.digitizeClicked)
        self.digitizeAction.setEnabled(False)
        self.toolbar.addAction(self.digitizeAction)
        self.iface.addPluginToMenu('Lat Lon Tools', self.digitizeAction)

        # Initialize the Settings Dialog Box
        settingsicon = QIcon(':/images/themes/default/mActionOptions.svg')
        self.settingsAction = QAction(settingsicon, "Settings", self.iface.mainWindow())
        self.settingsAction.setObjectName('latLonToolsSettings')
        self.settingsAction.setToolTip('Lat Lon Tools Settings')
        self.settingsAction.triggered.connect(self.settings)
        self.toolbar.addAction(self.settingsAction)
        self.iface.addPluginToMenu('Lat Lon Tools', self.settingsAction)

        # Help
        icon = QIcon(os.path.dirname(__file__) + '/images/help.svg')
        self.helpAction = QAction(icon, "Help", self.iface.mainWindow())
        self.helpAction.setObjectName('latLonToolsHelp')
        self.helpAction.triggered.connect(self.help)
        self.iface.addPluginToMenu('Lat Lon Tools', self.helpAction)

        self.iface.currentLayerChanged.connect(self.currentLayerChanged)
        self.canvas.mapToolSet.connect(self.resetTools)
        self.enableDigitizeTool()

        # Add the processing provider
        QgsApplication.processingRegistry().addProvider(self.provider)
        InitLatLonFunctions()

    def resetTools(self, newtool, oldtool):
        '''Uncheck the Copy Lat Lon tool'''
        try:
            if self.mapTool and (oldtool is self.mapTool):
                self.copyAction.setChecked(False)
            if self.showMapTool and (oldtool is self.showMapTool):
                self.externMapAction.setChecked(False)
            if newtool is self.mapTool:
                self.copyAction.setChecked(True)
            if newtool is self.showMapTool:
                self.externMapAction.setChecked(True)
        except Exception:
            pass

    def unload(self):
        '''Unload LatLonTools from the QGIS interface'''
        self.zoomToDialog.removeMarker()
        self.multiZoomDialog.removeMarkers()
        if self.mapTool:
            self.canvas.unsetMapTool(self.mapTool)
        if self.showMapTool:
            self.canvas.unsetMapTool(self.showMapTool)
        self.iface.removePluginMenu('Lat Lon Tools', self.copyAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.copyExtentsAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.externMapAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.zoomToAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.multiZoomToAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.convertCoordinatesAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.conversionsAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.settingsAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.helpAction)
        self.iface.removePluginMenu('Lat Lon Tools', self.digitizeAction)
        self.iface.removeDockWidget(self.zoomToDialog)
        self.iface.removeDockWidget(self.multiZoomDialog)
        # Remove Toolbar Icons
        self.iface.removeToolBarIcon(self.copyAction)
        self.iface.removeToolBarIcon(self.copyExtentToolbar)
        self.iface.removeToolBarIcon(self.zoomToAction)
        self.iface.removeToolBarIcon(self.externMapAction)
        self.iface.removeToolBarIcon(self.multiZoomToAction)
        self.iface.removeToolBarIcon(self.convertCoordinatesAction)
        self.iface.removeToolBarIcon(self.digitizeAction)
        del self.toolbar
        
        if self.convertCoordinateDialog:
            self.iface.removeDockWidget(self.convertCoordinateDialog)
            self.convertCoordinateDialog = None

        self.zoomToDialog = None
        self.multiZoomDialog = None
        self.settingsDialog = None
        self.showMapTool = None
        self.mapTool = None
        self.digitizerDialog = None
        QgsApplication.processingRegistry().removeProvider(self.provider)
        UnloadLatLonFunctions()

    def startCapture(self):
        '''Set the focus of the copy coordinate tool'''
        if self.mapTool is None:
            from .copyLatLonTool import CopyLatLonTool
            self.mapTool = CopyLatLonTool(self.settingsDialog, self.iface)
        self.canvas.setMapTool(self.mapTool)

    def copyExtentTriggered(self, action):
        self.copyExtentButton.setDefaultAction(action)
        
    def copyExtent(self):
        if self.copyExtentTool is None:
            from .captureExtent import CaptureExtentTool
            self.copyExtentTool = CaptureExtentTool(self.iface, self)
            self.copyExtentTool.setAction(self.copyExtentAction)
        self.canvas.setMapTool(self.copyExtentTool)

    def copyLayerExtent(self):
        layer = self.iface.activeLayer()
        if not layer or not layer.isValid():
            return
        if isinstance(layer, QgsVectorLayer) and (layer.featureCount() == 0):
            self.iface.messageBar().pushMessage("", "This layer has no features - A bounding box cannot be calculated.", level=Qgis.Warning, duration=4)
            return
        src_crs = layer.crs()
        extent = layer.extent()
        if settings.bBoxCrs == 0:
            dst_crs = epsg4326
        else:
            dst_crs = self.canvas.mapSettings().destinationCrs()
        
        outStr = getExtentString(extent, src_crs, dst_crs)
        clipboard = QApplication.clipboard()
        clipboard.setText(outStr)
        self.iface.messageBar().pushMessage("", "'{}' copied to the clipboard".format(outStr), level=Qgis.Info, duration=4)

    def copySelectedFeaturesExtent(self):
        layer = self.iface.activeLayer()
        if not layer or not layer.isValid():
            return
        if isinstance(layer, QgsVectorLayer) and (layer.featureCount() == 0):
            self.iface.messageBar().pushMessage("", "This layer has no features - A bounding box cannot be calculated.", level=Qgis.Warning, duration=4)
            return
        if isinstance(layer, QgsVectorLayer):
            extent = layer.boundingBoxOfSelected()
            if extent.isNull():
                self.iface.messageBar().pushMessage("", "No features were selected.", level=Qgis.Warning, duration=4)
                return
        else:
            extent = layer.extent()
        src_crs = layer.crs()
        if settings.bBoxCrs == 0:
            dst_crs = epsg4326
        else:
            dst_crs = self.canvas.mapSettings().destinationCrs()
        
        outStr = getExtentString(extent, src_crs, dst_crs)
        clipboard = QApplication.clipboard()
        clipboard.setText(outStr)
        self.iface.messageBar().pushMessage("", "'{}' copied to the clipboard".format(outStr), level=Qgis.Info, duration=4)

    def copyCanvas(self):
        extent = self.iface.mapCanvas().extent()
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if settings.bBoxCrs == 0:
            dst_crs = epsg4326
        else:
            dst_crs = canvas_crs
        
        outStr = getExtentString(extent, canvas_crs, dst_crs)
        clipboard = QApplication.clipboard()
        clipboard.setText(outStr)
        self.iface.messageBar().pushMessage("", "'{}' copied to the clipboard".format(outStr), level=Qgis.Info, duration=4)

    def setShowMapTool(self):
        '''Set the focus of the external map tool.'''
        if self.showMapTool is None:
            from .showOnMapTool import ShowOnMapTool
            self.showMapTool = ShowOnMapTool(self.iface)
        self.canvas.setMapTool(self.showMapTool)

    def showZoomToDialog(self):
        '''Show the zoom to docked widget.'''
        self.zoomToDialog.show()

    def convertCoordinatesTool(self):
        '''Display the Convert Coordinate Tool Dialog box.'''
        if self.convertCoordinateDialog is None:
            from .coordinateConverter import CoordinateConverterWidget
            self.convertCoordinateDialog = CoordinateConverterWidget(self, self.settingsDialog, self.iface, self.iface.mainWindow())
            self.convertCoordinateDialog.setFloating(True)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.convertCoordinateDialog)
        self.convertCoordinateDialog.show()

    def multiZoomTo(self):
        '''Display the Multi-zoom to dialog box'''
        self.multiZoomDialog.show()

    def field2geom(self):
        '''Convert layer containing a point x & y coordinate to a new point layer'''
        processing.execAlgorithmDialog('latlontools:field2geom', {})

    def geom2Field(self):
        '''Convert layer geometry to a text string'''
        processing.execAlgorithmDialog('latlontools:geom2field', {})

    def toMGRS(self):
        '''Display the to MGRS  dialog box'''
        processing.execAlgorithmDialog('latlontools:point2mgrs', {})

    def MGRStoLayer(self):
        '''Display the to MGRS  dialog box'''
        processing.execAlgorithmDialog('latlontools:mgrs2point', {})

    def toPlusCodes(self):
        processing.execAlgorithmDialog('latlontools:point2pluscodes', {})

    def PlusCodestoLayer(self):
        processing.execAlgorithmDialog('latlontools:pluscodes2point', {})

    def settings(self):
        '''Show the settings dialog box'''
        self.settingsDialog.show()

    def help(self):
        '''Display a help page'''
        import webbrowser
        url = QUrl.fromLocalFile(os.path.dirname(__file__) + "/index.html").toString()
        webbrowser.open(url, new=2)

    def settingsChanged(self):
        # Settings may have changed so we need to make sure the zoomToDialog window is configured properly
        self.zoomToDialog.configure()
        self.multiZoomDialog.settingsChanged()

    def zoomTo(self, src_crs, lat, lon):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(src_crs, canvas_crs, QgsProject.instance())
        x, y = transform.transform(float(lon), float(lat))

        rect = QgsRectangle(x, y, x, y)
        self.canvas.setExtent(rect)

        pt = QgsPointXY(x, y)
        self.highlight(pt)
        self.canvas.refresh()
        return pt

    def highlight(self, point):
        currExt = self.canvas.extent()

        leftPt = QgsPoint(currExt.xMinimum(), point.y())
        rightPt = QgsPoint(currExt.xMaximum(), point.y())

        topPt = QgsPoint(point.x(), currExt.yMaximum())
        bottomPt = QgsPoint(point.x(), currExt.yMinimum())

        horizLine = QgsGeometry.fromPolyline([leftPt, rightPt])
        vertLine = QgsGeometry.fromPolyline([topPt, bottomPt])

        self.crossRb.reset(QgsWkbTypes.LineGeometry)
        self.crossRb.addGeometry(horizLine, None)
        self.crossRb.addGeometry(vertLine, None)

        QTimer.singleShot(700, self.resetRubberbands)

    def resetRubberbands(self):
        self.crossRb.reset()

    def digitizeClicked(self):
        if self.digitizerDialog is None:
            from .digitizer import DigitizerWidget
            self.digitizerDialog = DigitizerWidget(self, self.iface, self.iface.mainWindow())
        self.digitizerDialog.show()

    def currentLayerChanged(self):
        layer = self.iface.activeLayer()
        if layer is not None:
            try:
                layer.editingStarted.disconnect(self.layerEditingChanged)
            except Exception:
                pass
            try:
                layer.editingStopped.disconnect(self.layerEditingChanged)
            except Exception:
                pass

            if isinstance(layer, QgsVectorLayer):
                layer.editingStarted.connect(self.layerEditingChanged)
                layer.editingStopped.connect(self.layerEditingChanged)

        self.enableDigitizeTool()

    def layerEditingChanged(self):
        self.enableDigitizeTool()

    def enableDigitizeTool(self):
        self.digitizeAction.setEnabled(False)
        layer = self.iface.activeLayer()

        if layer is not None and isinstance(layer, QgsVectorLayer) and (layer.geometryType() == QgsWkbTypes.PointGeometry) and layer.isEditable():
            self.digitizeAction.setEnabled(True)
        else:
            if self.digitizerDialog is not None:
                self.digitizerDialog.close()
