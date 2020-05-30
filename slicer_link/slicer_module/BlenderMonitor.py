from __main__ import vtk, qt, ctk, slicer

import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree
from xml.etree import ElementTree as ET
import re

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
        parent.contributors = ["Patrick Moore"] # replace with "Firstname Lastname (Org)"
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
        modelNodeSelector.connect('currentNodeChanged(bool)', self.send_model_to_blender)
        self.sampleFormLayout.addRow("Sync Model:", modelNodeSelector)
        self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)', modelNodeSelector, 'setMRMLScene(vtkMRMLScene*)')
        modelNodeSelector.setMRMLScene(slicer.mrmlScene)
        self.SlicerSelectedModelsList.append(modelNodeSelector)

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
            
    def send_model_to_blender(self):
        pass
    
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


