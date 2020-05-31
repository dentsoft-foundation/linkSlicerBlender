"""
@author: Patrick R. Moore, Georgi Talmazov

"""

from __main__ import vtk, qt, ctk, slicer

import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree, tostring
from xml.etree import ElementTree as ET
import re
import numpy as np

#http://codeprogress.com/python/libraries/pyqt/showPyQTExample.php?index=419&key=QFileSystemWatcherDirChange&version=4
#http://stackoverflow.com/questions/32097163/pyqt-qfilesystemwatcher-doesnt-capture-the-file-added
#http://codereview.stackexchange.com/questions/104555/directory-watcher-and-notifier-for-files-added-or-removed
#http://codereview.stackexchange.com/questions/104555/directory-watcher-and-notifier-for-files-added-or-removed
#https://github.com/Slicer/Slicer/blob/master/Extensions/Testing/ScriptedLoadableExtensionTemplate/ScriptedLoadableModuleTemplate/ScriptedLoadableModuleTemplate.py

#how to use QTimer
#http://pyqt.sourceforge.net/Docs/PyQt4/qtimer.html
#Endoscopy Thread has QTimer example

from comm import asyncsock

def xor(lst1, lst2):
    """ returns a tuple of items of item not in either of lists
    """
    x = lst2 if len(lst2) > len(lst1) else lst1
    y = lst1 if len(lst1) < len(lst2) else lst2
    return tuple(item for item in x if item not in y)

class BlenderMonitor:
    def __init__(self, parent):
        parent.title = "Blender Monitor"
        parent.categories = ["Examples"]
        parent.dependencies = []
        parent.contributors = ["Patrick Moore", "Georgi Talmazov (Dental Software Foundation)"] # replace with "Firstname Lastname (Org)"
        parent.helpText = """
        Example of scripted loadable extension for the HelloPython tutorial that monitors a directory for file changes.
        """
        parent.acknowledgementText = """Independently developed for the good of the world""" # replace with organization, grant and thanks.
        self.parent = parent

#
# qHelloPythonWidget
#

class BlenderMonitorWidget:
    def __init__(self, parent = None):
        if not parent:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
        else:
            self.parent = parent
        self.layout = self.parent.layout()
        if not parent:
            self.setup()
            self.parent.show()

        self.watching = False
        self.sock = None
        self.SlicerSelectedModelsList = []
        #self.toSync = []
        
    def setup(self):
        # Instantiate and connect widgets ...
        
        # Collapsible button
        sampleCollapsibleButton = ctk.ctkCollapsibleButton()
        sampleCollapsibleButton.text = "Configuration:"
        self.layout.addWidget(sampleCollapsibleButton)

        # Layout within the sample collapsible button
        self.sampleFormLayout = qt.QFormLayout(sampleCollapsibleButton)

        #directory selector
        self.outputDirSelector = ctk.ctkPathLineEdit()
        self.outputDirSelector.filters = ctk.ctkPathLineEdit.Dirs
        self.outputDirSelector.settingKey = 'BlenderMonitorDir'
        self.sampleFormLayout.addRow("tmp dir:", self.outputDirSelector)
        
        if not self.outputDirSelector.currentPath:
            self_dir = os.path.dirname(os.path.abspath(__file__))
            defaultOutputPath = os.path.join(self_dir, "tmp")
                       
            if not os.path.exists(defaultOutputPath):
                print(defaultOutputPath)                  
                defaultOutputPath = slicer.app.defaultScenePath
                
            self.outputDirSelector.setCurrentPath(defaultOutputPath)
            
        self.host_address = qt.QLineEdit()
        self.host_address.setText(str(asyncsock.address[0]))
        self.sampleFormLayout.addRow("Host:", self.host_address)
        
        self.host_port = qt.QLineEdit()
        self.host_port.setText(str(asyncsock.address[1]))
        self.sampleFormLayout.addRow("Port:", self.host_port)

        # connect button
        playButton = qt.QPushButton("Connect")
        playButton.toolTip = "Connect to configured server."
        playButton.checkable = True
        self.sampleFormLayout.addRow(playButton)
        playButton.connect('toggled(bool)', self.onPlayButtonToggled)
        self.playButton = playButton

        #Models list
        addModelButton = qt.QPushButton("Add Model")
        addModelButton.toolTip = "Add a model to the list to sync with Blender."
        self.sampleFormLayout.addRow(addModelButton)
        addModelButton.connect('clicked()', self.onaddModelButtonToggled)
        
        """
        #Report Window           
        self.text_report = qt.QTextEdit()
        self.text_report.setText('Report file changes here')
        self.sampleFormLayout.addRow('Dir Status:', self.text_report)
        """

    def onaddModelButtonToggled(self):
        modelNodeSelector = slicer.qMRMLNodeComboBox()
        modelNodeSelector.objectName = 'modelNodeSelector'
        modelNodeSelector.toolTip = "Select a model."
        modelNodeSelector.nodeTypes = ['vtkMRMLModelNode']
        modelNodeSelector.noneEnabled = True
        modelNodeSelector.addEnabled = True
        modelNodeSelector.removeEnabled = True
        modelNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.send_model_to_blender)
        self.sampleFormLayout.addRow("Link Model:", modelNodeSelector)

        #model delete button
        ModelDeleteButton = qt.QPushButton("Unlink Model")
        ModelDeleteButton.toolTip = "Unlink selected model from blender."
        ModelDeleteButton.checkable = True
        self.sampleFormLayout.addRow(ModelDeleteButton)
        ModelDeleteButton.connect('toggled(bool)', self.onModelDeleteToggled)

        self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)', modelNodeSelector, 'setMRMLScene(vtkMRMLScene*)')
        modelNodeSelector.setMRMLScene(slicer.mrmlScene)
        self.SlicerSelectedModelsList.append(modelNodeSelector)
        
    def onModelDeleteToggled(self):
        pass

    def update_scene(self, xml):
        if not self.watching: return
        
        #find the temp directory
        self_dir = os.path.dirname(os.path.abspath(__file__))
        tmp_dir = os.path.join(self_dir, "tmp")
        
        if not os.path.exists(tmp_dir):
            print('there is no temporary directory')
            print('there needs to be a folder named "tmp"')
            print('it should be in same folder with this script')
            print('this script is located here')
            print(self_dir)
            return

        #my_file = open(scene_file)
        tree = ET.ElementTree(ET.fromstring(xml))
        x_scene = tree.getroot()
        #my_file.close()
        
        s_scene = slicer.mrmlScene
        #scene = slicer.mrmlScene
        for b_ob in x_scene:
            #get the name of blender object
            name = b_ob.get('name')
        
            #check if there is the same sicer model in the scene
            try:
                slicer_model = slicer.util.getNode(name)
            except slicer.util.MRMLNodeNotFoundException:
                slicer_model = None
            
            if not slicer_model:                
                ob_file = os.path.join(tmp_dir, name + ".ply")
                if os.path.exists(ob_file):
                    print(name + ' loading model from .ply')
                    ret = slicer.util.loadModel(ob_file)
                    if not ret:
                        print('could not load the ply model')
                    slicer_model = slicer.util.getNode(name)
                    if not slicer_model: continue
                    
                    disp_node = slicer_model.GetDisplayNode()
                    disp_node.SetSliceIntersectionVisibility(True)
                    disp_node.SetSliceIntersectionThickness(2)
                    
                    mat = b_ob.find('material')
                    if mat is not None: 
                        r, g, b = mat.find('r').text, mat.find('g').text, mat.find('b').text
                        disp_node.SetColor(float(r),float(g),float(b))
                else:
                    continue
            
            xml_mx = b_ob.find('matrix')
            
            #try to get transform node
            try:
                transform = slicer.util.getNode(name+'_trans')
            except slicer.util.MRMLNodeNotFoundException:
                transform = None
                
            if not transform:
                transform = slicer.vtkMRMLTransformNode()
                transform.SetName(name+'_trans')        
                s_scene.AddNode(transform)
            
            slicer_model.SetAndObserveTransformNodeID(transform.GetID())
        
            #set the elements of transform form the matrix
            #my_matrix = vtk.vtkMatrix4x4()
            my_matrix = transform.GetMatrixTransformFromParent()
            for i in range(0,4):
                for j in range(0,4):
                    my_matrix.SetElement(i,j,float(xml_mx[i][j].text))
        
            #update object location in scene
            transform.SetAndObserveMatrixTransformToParent(my_matrix)
            
    def send_model_to_blender(self, modelNodeSelector):
        if not self.SlicerSelectedModelsList == []:
            modelNode = modelNodeSelector #.currentNode()
            modelNode.CreateDefaultDisplayNodes()
            #str_list = ""
            #for row in slicer.util.arrayFromModelPoints(modelNode):
            #    str_list += ", ".join(row)
            #    str_list = "[" + str_list + "], "
            #model_bytes_str = "[" + str_list + "]"
            model_bytes_str = str(slicer.util.arrayFromModelPoints(modelNode).tolist())
            xml_str = "%s_XML_DATA_%s"%(model_bytes_str, tostring(self.build_xml_scene()).decode())
            packet = model_bytes_str + xml_str
            self.sock.send_data("OBJ", xml_str)

    def matrix_to_xml_element(self, mx):
        nrow = len(mx)
        ncol = len(mx[0])
        
        xml_mx = Element('matrix')
        
        for i in range(0,nrow):
            xml_row = SubElement(xml_mx, 'row')
            for j in range(0,ncol):
                mx_entry = SubElement(xml_row, 'entry')
                mx_entry.text = str(mx[i][j])
                
        return xml_mx

    def arrayFromVTKMatrix(self, vmatrix):
        """Return vtkMatrix4x4 or vtkMatrix3x3 elements as numpy array.
        The returned array is just a copy and so any modification in the array will not affect the input matrix.
        To set VTK matrix from a numpy array, use :py:meth:`vtkMatrixFromArray` or
        :py:meth:`updateVTKMatrixFromArray`.
        """
        if isinstance(vmatrix, vtk.vtkMatrix4x4):
            matrixSize = 4
        elif isinstance(vmatrix, vtk.vtkMatrix3x3):
            matrixSize = 3
        else:
            raise RuntimeError("Input must be vtk.vtkMatrix3x3 or vtk.vtkMatrix4x4")
        narray = np.eye(matrixSize)
        vmatrix.DeepCopy(narray.ravel(), vmatrix)
        return narray.tolist()

    def build_xml_scene(self):
        '''
        obs - list of slicer objects
        file - filepath to write the xml
        builds the XML scene of all object in self.SlicerSelectedModelsList
        '''
            
        x_scene = Element('scene')

        s_scene = slicer.mrmlScene
        for model in self.SlicerSelectedModelsList:
            if model.currentNode() is not None:
                #print(model.currentNode())
                #name = model.currentNode().GetName()
                #try to get transform node
                try:
                    transform = slicer.util.getNode(model.currentNode().GetName()+'_trans')
                except slicer.util.MRMLNodeNotFoundException:
                    transform = None
                    
                if not transform:
                    transform = slicer.vtkMRMLTransformNode()
                    transform.SetName(model.currentNode().GetName()+'_trans')        
                    s_scene.AddNode(transform)
                model.currentNode().SetAndObserveTransformNodeID(transform.GetID())

                #self.PLYexport(model.currentNode())

                xob = SubElement(x_scene, 'b_object')
                xob.set('name', model.currentNode().GetName())
                

                my_matrix = transform.GetMatrixTransformFromParent()
                xmlmx = self.matrix_to_xml_element(self.arrayFromVTKMatrix(my_matrix))
                xob.extend([xmlmx])
                        
        return x_scene

    def PLYexport(self, modelNode):
        #modelNode = getNode(model)
        plyFilePath = self.outputDirSelector.currentPath + "\\" + modelNode.GetName() + ".ply"
        print (plyFilePath)
        modelDisplayNode = modelNode.GetDisplayNode()
        triangles = vtk.vtkTriangleFilter()
        triangles.SetInputConnection(modelDisplayNode.GetOutputPolyDataConnection())

        plyWriter = vtk.vtkPLYWriter()
        plyWriter.SetInputConnection(triangles.GetOutputPort())
        lut = vtk.vtkLookupTable()
        #lut.DeepCopy(modelDisplayNode.GetColorNode().GetLookupTable())
        lut.SetRange(modelDisplayNode.GetScalarRange())
        plyWriter.SetLookupTable(lut)
        plyWriter.SetArrayName(modelDisplayNode.GetActiveScalarName())

        plyWriter.SetFileName(plyFilePath)
        plyWriter.Write()
        #plyWriter.Close() #does the write release/close/free automatically?
        #return modelNode

    def onPlayButtonToggled(self, checked):
        if checked:
            self.watching = True
            self.playButton.text = "Stop"
            if self.sock == None:
                self.sock = asyncsock.SlicerComm.EchoClient(str(self.host_address.text), int(self.host_port.text), [("XML", self.update_scene)])
                self.sock.send_data("TEST", 'bogus data from slicer!')
        else:
            self.watching = False
            self.playButton.text = "Start"
            self.sock.handle_close()
            
            #TODO
                
    def frameDelaySliderValueChanged(self, newValue):
        #print "frameDelaySliderValueChanged:", newValue
        self.timer.interval = newValue


