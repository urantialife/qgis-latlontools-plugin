import os
import re

from PyQt4.QtGui import ( QIcon, QDockWidget, QHeaderView, 
    QAbstractItemView, QFileDialog, QTableWidgetItem,
    QMessageBox)
from PyQt4.uic import loadUiType
from PyQt4.QtCore import Qt, QVariant, pyqtSlot
from qgis.core import ( QgsCoordinateTransform, QgsVectorLayer,
    QgsField, QgsFeature, QgsPoint, QgsGeometry, 
    QgsPalLayerSettings, QgsMapLayerRegistry )
from qgis.gui import QgsVertexMarker, QgsMessageBar
from LatLon import LatLon

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui/multiZoomDialog.ui'))

LABELS = ['Latitude','Longitude','Label','Data1','Data2','Data3',
    'Data4','Data5','Data6','Data7','Data8','Data9','Data10']

MAXDATA = 10

class MultiZoomWidget(QDockWidget, FORM_CLASS):
    '''Multizoom Dialog box.'''
    def __init__(self, lltools, settings, parent):
        super(MultiZoomWidget, self).__init__(parent)
        self.setupUi(self)
        self.settings = settings
        self.iface = lltools.iface
        self.canvas = self.iface.mapCanvas()
        self.lltools = lltools
        self.llitems=[]
        
        # Set up a connection with the coordinate capture tool
        self.lltools.mapTool.capturesig.connect(self.capturedPoint)
        
        self.addButton.setIcon(QIcon(os.path.dirname(__file__) + "/images/check.png"))
        self.coordCaptureButton.setIcon(QIcon(os.path.dirname(__file__) + "/images/coordinate_capture.png"))
        self.coordCaptureButton.clicked.connect(self.startCapture)
        self.openButton.setIcon(QIcon(':/images/themes/default/mActionFileOpen.svg'))
        self.saveButton.setIcon(QIcon(':/images/themes/default/mActionFileSave.svg'))
        self.removeButton.setIcon(QIcon(':/images/themes/default/mActionDeleteSelected.svg'))
        self.clearAllButton.setIcon(QIcon(':/images/themes/default/mActionDeselectAll.svg'))
        self.createLayerButton.setIcon(QIcon(':/images/themes/default/mActionNewVectorLayer.svg'))
        self.optionsButton.setIcon(QIcon(':/images/themes/default/mActionOptions.svg'))
        
        self.openButton.clicked.connect(self.openDialog)
        self.saveButton.clicked.connect(self.saveDialog)
        self.addButton.clicked.connect(self.addSingleCoord)
        self.removeButton.clicked.connect(self.removeTableRow)
        self.addLineEdit.returnPressed.connect(self.addSingleCoord)
        self.clearAllButton.clicked.connect(self.clearAll)
        self.createLayerButton.clicked.connect(self.createLayer)
        self.optionsButton.clicked.connect(self.showSettings)
        self.showAllCheckBox.stateChanged.connect(self.updateDisplayedMarkers)
        self.dirname = ''
        self.numcoord = 0
        self.maxResults = 5000
        self.numCol = 3 + self.settings.multiZoomNumCol
        self.resultsTable.setColumnCount(self.numCol)
        self.resultsTable.setSortingEnabled(False)
        self.resultsTable.setHorizontalHeaderLabels(LABELS[0:self.numCol])
        self.resultsTable.horizontalHeader().setResizeMode(QHeaderView.Stretch)
        self.resultsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resultsTable.cellClicked.connect(self.itemClicked)
        self.resultsTable.cellChanged.connect(self.cellChanged)
        self.resultsTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.resultsTable.horizontalHeader().geometriesChanged.connect(self.geomChanged)

    def settingsChanged(self):
        if self.numCol != self.settings.multiZoomNumCol + 3:
            self.numCol = 3 + self.settings.multiZoomNumCol
            self.resultsTable.blockSignals(True)
            self.resultsTable.setColumnCount(self.numCol)
            self.resultsTable.setHorizontalHeaderLabels(LABELS[0:self.numCol])
            for i, ll in enumerate(self.llitems):
                item = QTableWidgetItem(str(ll.lat))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.resultsTable.setItem(i, 0, item)
                item = QTableWidgetItem(str(ll.lon))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.resultsTable.setItem(i, 1, item)
                self.resultsTable.setItem(i, 2, QTableWidgetItem(ll.label))
                if self.numCol > 3:
                    for j in range(3,self.numCol):
                        self.resultsTable.setItem(i, j, QTableWidgetItem(ll.data[j-3]))
                
            self.resultsTable.clearSelection()
            self.resultsTable.blockSignals(False)
            self.geomChanged()
            self.updateDisplayedMarkers()
        
        
    def closeEvent(self, e):
        '''Called when the dialog box is being closed. We want to clear selected features and remove
           all the markers.'''
        self.resultsTable.clearSelection()
        self.removeMarkers()
        self.stopCapture()
        self.hide()
        
    def showEvent(self, e):
        '''The dialog box is going to be displayed so we need to check to
           see if markers need to be displayed.'''
        self.updateDisplayedMarkers()
        self.resultsTable.horizontalHeader().setResizeMode(QHeaderView.Interactive)
        self.setEnabled(True)

    def geomChanged(self):
        '''This will force the columns to be stretched to the full width
           when the dialog geometry changes, but will then set it so that the user
           can adjust them.'''
        self.resultsTable.horizontalHeader().setResizeMode(QHeaderView.Stretch)
        self.resultsTable.horizontalHeader().resizeSections()
        self.resultsTable.horizontalHeader().setResizeMode(QHeaderView.Interactive)
    
    @pyqtSlot(QgsPoint)
    def capturedPoint(self, pt):
        self.resultsTable.clearSelection()
        newrow = self.addCoord(pt.y(), pt.x())
        self.resultsTable.selectRow(newrow)
        self.updateDisplayedMarkers()

    def startCapture(self):
        if self.coordCaptureButton.isChecked():
            self.lltools.mapTool.capture4326 = True
            self.lltools.startCapture()
        else:
            self.lltools.mapTool.capture4326 = False
        
    def stopCapture(self):
        self.lltools.mapTool.capture4326 = False
        self.coordCaptureButton.setChecked(False)
        
    def clearAll(self):
        reply = QMessageBox.question(self, 'Message',
            'Are your sure you want to delete all entries?',
            QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.removeMarkers()
            self.llitems=[]
            self.resultsTable.setRowCount(0)
            self.numcoord = 0
        
    def showSettings(self):
        self.settings.showTab(3)
        
    def updateDisplayedMarkers(self):
        selectedRow = self.resultsTable.currentRow()
        # If the row is not selected we do not want to display the marker
        indices = [x.row() for x in self.resultsTable.selectionModel().selectedRows()]
        if not selectedRow in indices:
            selectedRow = -1
        if self.showAllCheckBox.checkState():
            for item in self.llitems:
                if item.marker is None:
                    item.marker = QgsVertexMarker(self.canvas)
                    pt = self.canvasPoint(item.lat, item.lon)
                    item.marker.setCenter(pt)
                    item.marker.setIconSize(18)
                    item.marker.setPenWidth(2)
                    item.marker.setIconType(QgsVertexMarker.ICON_CROSS)
        else: # Only a selected row will be displayed
            for id, item in enumerate(self.llitems):
                if id == selectedRow:
                    if item.marker is None:
                        item.marker = QgsVertexMarker(self.canvas)
                        pt = self.canvasPoint(item.lat, item.lon)
                        item.marker.setCenter(pt)
                        item.marker.setIconSize(18)
                        item.marker.setPenWidth(2)
                        item.marker.setIconType(QgsVertexMarker.ICON_CROSS)
                elif item.marker is not None:
                    self.canvas.scene().removeItem(item.marker)
                    item.marker = None
        
    def removeMarkers(self):
        if self.numcoord == 0:
            return
        for item in self.llitems:
            if item.marker is not None:
                self.canvas.scene().removeItem(item.marker)
                item.marker = None
        
    def removeMarker(self, row):
        if row >= len(self.llitems):
            return
        if self.llitems[row].marker is not None:
            self.canvas.scene().removeItem(self.llitems[row].marker)
            self.llitems[row].marker = None
        
    def openDialog(self):
        filename = QFileDialog.getOpenFileName(None, "Input File", 
                self.dirname, "Text, CSV (*.txt *.csv);;All files (*.*)")
        if filename:
            self.dirname = os.path.dirname(filename)
            self.readFile(filename)
        
    def saveDialog(self):
        filename = QFileDialog.getSaveFileName(None, "Save File", 
                self.dirname, "Text CSV (*.csv)")
        if filename:
            self.dirname = os.path.dirname(filename)
            self.saveFile(filename)
            
    def readFile(self, fname):
        '''Read a file of coordinates and add them to the list.'''
        try:
            with open(fname) as f:
                for line in f:
                    try:
                        parts = [x.strip() for x in line.split(',')]
                        if len(parts) >=2:
                            lat = LatLon.parseDMSStringSingle(parts[0])
                            lon = LatLon.parseDMSStringSingle(parts[1])
                            label = ''
                            data = []
                            if len(parts) >= 3:
                                label = parts[2]
                            if len(parts) >= 4:
                                data = parts[3:]
                            self.addCoord(lat, lon, label, data)
                    except:
                        pass
        except:
            pass
        self.updateDisplayedMarkers()
    
    def saveFile(self, fname):
        '''Save the zoom locations'''
        if self.numcoord == 0:
            return
        with open(fname,'w') as f:
            for item in self.llitems:
                s = "{},{},{}".format(item.lat, item.lon, item.label)
                f.write(s)
                if self.numCol >= 4:
                    for i in range(self.numCol - 3):
                        s = ",{}".format(item.data[i])
                        f.write(s)
                f.write('\n')
        f.close()
            
        
    def removeTableRow(self):
        '''Remove an entry from the coordinate table.'''
        row = int(self.resultsTable.currentRow())
        indices = [x.row() for x in self.resultsTable.selectionModel().selectedRows()]
        # Need to check to see if a row has been selected and that it is actually selected.
        # currentRow() will return the last selected row even though it may have been deleted.
        if row < 0 or not row in indices:
            return
        self.removeMarker(row)
        self.resultsTable.removeRow(row)
        del self.llitems[row]
        self.resultsTable.clearSelection()
        self.numcoord -= 1
        
    
    def addSingleCoord(self):
        '''Add a coordinate that was pasted into the coordinate text box.'''
        parts = [x.strip() for x in self.addLineEdit.text().split(',')]
        label = ''
        data = []
        numFields = len(parts)
        try:
            if numFields >= 2:
                lat = LatLon.parseDMSStringSingle(parts[0])
                lon = LatLon.parseDMSStringSingle(parts[1])
                if numFields >= 3:
                    label = parts[2]
                if numFields >= 4:
                    data = parts[3:]
                    
            else:
                self.iface.messageBar().pushMessage("", "Invalid Coordinate" , level=QgsMessageBar.WARNING, duration=3)
                return
        except:
            if self.addLineEdit.text():
                self.iface.messageBar().pushMessage("", "Invalid Coordinate" , level=QgsMessageBar.WARNING, duration=3)
            return
        newrow = self.addCoord(lat, lon, label, data)
        self.addLineEdit.clear()
        self.resultsTable.selectRow(newrow)
        self.updateDisplayedMarkers()
        
    def addCoord(self, lat, lon, label='', data=[]):
        '''Add a coordinate to the list.'''
        if self.numcoord >= self.maxResults:
            return
        self.resultsTable.insertRow(self.numcoord)
        self.llitems.append(LatLonItem(lat, lon, label, data))
        self.resultsTable.blockSignals(True)
        item = QTableWidgetItem(str(lat))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.resultsTable.setItem(self.numcoord, 0, item)
        item = QTableWidgetItem(str(lon))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.resultsTable.setItem(self.numcoord, 1, item)
        self.resultsTable.setItem(self.numcoord, 2, QTableWidgetItem(label))
        if self.numCol > 3 and len(data) > 0:
            for i in range( min(self.numCol-3, len(data))):
                self.resultsTable.setItem(self.numcoord, i+3, QTableWidgetItem(data[i]))
            
        self.resultsTable.blockSignals(False)
        self.numcoord += 1
        return(self.numcoord-1)
        
    def itemClicked(self, row, col):
        '''An item has been click on so zoom to it'''
        self.updateDisplayedMarkers()
        selectedRow = self.resultsTable.currentRow()
        # Call the the parent's zoom to function
        pt = self.lltools.zoomTo(self.settings.epsg4326, self.llitems[selectedRow].lat,self.llitems[selectedRow].lon)
        
    def canvasPoint(self, lat, lon):
        canvasCrs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(self.settings.epsg4326, canvasCrs)
        x, y = transform.transform(float(lon), float(lat))
        pt = QgsPoint(x,y)
        return pt

        
    def cellChanged(self, row, col):
        if col == 2:
            self.llitems[row].label = self.resultsTable.item(row, col).text()
        elif col >= 3:
            self.llitems[row].data[col-3] = self.resultsTable.item(row, col).text()
            
    def createLayer(self):
        '''Create a memory layer from the zoom to locations'''
        if self.numcoord == 0:
            return
        attr = []
        for item, label in enumerate(LABELS[0:self.numCol]):
            label = label.lower()
            if item <= 1:
                attr.append(QgsField(label, QVariant.Double))
            else:
                attr.append(QgsField(label, QVariant.String))
        ptLayer = QgsVectorLayer("Point?crs=epsg:4326", u"Lat Lon Locations", "memory")
        provider = ptLayer.dataProvider()
        provider.addAttributes(attr)
        ptLayer.updateFields()
        
        for item in self.llitems:
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(item.lon,item.lat)))
            attr = [item.lat, item.lon, item.label]
            for i in range(3,self.numCol):
                attr.append(item.data[i-3])
            feature.setAttributes(attr)
            provider.addFeatures([feature])
        
        ptLayer.updateExtents()
        if self.settings.multiZoomStyleID == 1:
            label = QgsPalLayerSettings()
            label.readFromLayer(ptLayer)
            label.enabled = True
            label.fieldName = 'label'
            label.placement= QgsPalLayerSettings.AroundPoint
            label.writeToLayer(ptLayer)
        elif self.settings.multiZoomStyleID == 2 and os.path.isfile(self.settings.customQMLFile()):
            ptLayer.loadNamedStyle(self.settings.customQMLFile())
            
        QgsMapLayerRegistry.instance().addMapLayer(ptLayer)
        
class LatLonItem():
    def __init__(self, lat, lon, label='', data=[]):
        self.lat = lat
        self.lon = lon
        self.label = label
        self.data = ['']*MAXDATA
        for i, d in enumerate(data):
            if i < MAXDATA:
                self.data[i] = d
        self.marker = None
