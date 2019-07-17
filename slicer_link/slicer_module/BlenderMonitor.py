from __main__ import vtk, qt, ctk, slicer

import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree
from xml.etree import ElementTree as ET


#http://codeprogress.com/python/libraries/pyqt/showPyQTExample.php?index=419&key=QFileSystemWatcherDirChange&version=4
#http://stackoverflow.com/questions/32097163/pyqt-qfilesystemwatcher-doesnt-capture-the-file-added
#http://codereview.stackexchange.com/questions/104555/directory-watcher-and-notifier-for-files-added-or-removed
#http://codereview.stackexchange.com/questions/104555/directory-watcher-and-notifier-for-files-added-or-removed
#https://github.com/Slicer/Slicer/blob/master/Extensions/Testing/ScriptedLoadableExtensionTemplate/ScriptedLoadableModuleTemplate/ScriptedLoadableModuleTemplate.py

#how to use QTimer
#http://pyqt.sourceforge.net/Docs/PyQt4/qtimer.html
#Endoscopy Thread has QTimer example



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
        self.file_monitor = None  #don't monitor until told to
        self._initialContent = []
            
        #self.timer = qt.QTimer()
        #self.timer.setInterval(1000)
        #self.timer.connect('timeout()', self.onTimerEvent)
        #self.timer_count = 0
    
        #TODO adjustabel refresh rate
        #TODO start button
        #TODO stop button and cleanup timer
        
        
    def setup(self):
        # Instantiate and connect widgets ...
        
        # Collapsible button
        sampleCollapsibleButton = ctk.ctkCollapsibleButton()
        sampleCollapsibleButton.text = "Directory to Monitor"
        self.layout.addWidget(sampleCollapsibleButton)

        # Layout within the sample collapsible button
        sampleFormLayout = qt.QFormLayout(sampleCollapsibleButton)

        #directory selector
        self.outputDirSelector = ctk.ctkPathLineEdit()
        self.outputDirSelector.filters = ctk.ctkPathLineEdit.Dirs
        self.outputDirSelector.settingKey = 'BlenderMonitorDir'
        sampleFormLayout.addRow("Blender tmp directory:", self.outputDirSelector)
        
        if not self.outputDirSelector.currentPath:
            self_dir = os.path.dirname(os.path.abspath(__file__))
            defaultOutputPath = os.path.join(self_dir, "tmp")
                       
            if not os.path.exists(defaultOutputPath):
                print(defaultOutputPath)                  
                defaultOutputPath = slicer.app.defaultScenePath
                
            self.outputDirSelector.setCurrentPath(defaultOutputPath)
            
        # Play button
        playButton = qt.QPushButton("Start")
        playButton.toolTip = "Start Monitoring Directory."
        playButton.checkable = True
        sampleFormLayout.addRow(playButton)
        playButton.connect('toggled(bool)', self.onPlayButtonToggled)
        self.playButton = playButton
        
        #Report Window           
        self.text_report = qt.QTextEdit()
        self.text_report.setText('Report file changes here')
        sampleFormLayout.addRow('Dir Status:', self.text_report)
        # HelloWorld button
        #helloWorldButton = qt.QPushButton("Import Blender")
        #helloWorldButton.toolTip = "Print 'Hello world' in standard ouput."
        #sampleFormLayout.addWidget(helloWorldButton)
        #helloWorldButton.connect('clicked(bool)', self.onHelloWorldButtonClicked)
    
        # Add vertical spacer
        #self.layout.addStretch(1)

        # Set local var as instance attribute
        #self.helloWorldButton = helloWorldButton

        
    
     
    def slotDirChanged(self, path):
        newContent = ''.join(xor(os.listdir(path), self._initialContent))

        #careful not to create an infinite or do loop
        if 'update.txt' in newContent and 'update.txt' in self._initialContent:
            
            print('update in new and initial content...?')
            print('why havent I update yet?')
            print('did I just remove update.txt')
            print(os.listdir(path))
            return
        
        elif 'update.txt' in newContent and 'update.txt' not in self._initialContent:
            update_file = os.path.join(path, 'update.txt')
            
            #read any xml file, and do what is neeeded
            self.onHelloWorldButtonClicked()
            
            #delete the update signal
            os.remove(update_file)
            
        elif 'closed.txt' in newContent and 'closed.txt' not in self._initialContent:
            self.text_report.setText("Blender file has changed!  Link has been disconnected")
        
        self._initialContent = os.listdir(path)
        msg = ""
        if newContent not in self._initialContent:
            msg = "removed: %s" % newContent
        else:
            msg = "added: %s" %  newContent
        self.text_report.setText("Detected Directory Change!! \n %s" % msg)
    
    def connectSignals(self):
        self.file_monitor.directoryChanged.connect(self.slotDirChanged)
        
    def onHelloWorldButtonClicked(self):
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
        
        scene_file = os.path.join(tmp_dir, "blend_to_slicer.xml")
        print(scene_file)
        if not os.path.exists(scene_file):
            print('NO XML FILE IN THE TEMP DIRECOTRY')
            print("Export scene from Blender")
            print("it needs to be stored in the following directory")
            print(tmp_dir)
            return
        
        my_file = open(scene_file)
        tree = ET.parse(my_file)
        x_scene = tree.getroot()
        my_file.close()
        
        s_scene = slicer.mrmlScene
        #scene = slicer.mrmlScene
        for b_ob in x_scene:
            #get the name of blender object
            name = b_ob.get('name')
        
            #check if there is the same sicer model in the scene
            slicer_model = slicer.util.getNode(name)
            
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
            transform = slicer.util.getNode(name+'_trans')
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

    
    def onPlayButtonToggled(self, checked):
        if checked:
            self.watching = True
            self.playButton.text = "Stop"
            if self.file_monitor == None:
                fileSysWatcher  = qt.QFileSystemWatcher()
                fileSysWatcher.addPath(self.outputDirSelector.currentPath)
                fileSysWatcher.addPath(self.outputDirSelector.currentPath.replace("\\","/")) 
                self.file_monitor = fileSysWatcher
                self.connectSignals()

                self._initialContent = os.listdir(self.outputDirSelector.currentPath)
                self.onHelloWorldButtonClicked()
                
                
                update_file = os.path.join(self.outputDirSelector.currentPath, 'update.txt')
                if os.path.exists(update_file):
                    #delete the update signal
                    os.remove(update_file)
                    self._initialContent = os.listdir(self.outputDirSelector.currentPath)
                else:
                    print('Unable to delete update file because it does not exist?')
                    print(update_file)
                    print(os.listdir(self.outputDirSelector.currentPath))
                #TODO, import models and what not?
                #TODO, update outputDirSelctor.currentPath if needed
        else:
            self.watching = False
            self.playButton.text = "Start"
            
            #TODO
                
    def frameDelaySliderValueChanged(self, newValue):
        #print "frameDelaySliderValueChanged:", newValue
        self.timer.interval = newValue