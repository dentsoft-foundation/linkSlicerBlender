from __main__ import vtk, qt, ctk, slicer

import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree
from xml.etree import ElementTree as ET


#http://codeprogress.com/python/libraries/pyqt/showPyQTExample.php?index=419&key=QFileSystemWatcherDirChange&version=4
#http://codereview.stackexchange.com/questions/104555/directory-watcher-and-notifier-for-files-added-or-removed


# HelloPython
#
def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


class BlenderLink:
    def __init__(self, parent):
        parent.title = "Blender Scene"
        parent.categories = ["Examples"]
        parent.dependencies = []
        parent.contributors = ["Patrick Moore"] # replace with "Firstname Lastname (Org)"
        parent.helpText = """
        Example of scripted loadable extension for the HelloPython tutorial.
        """
        parent.acknowledgementText = """Independently developed for the good of the world""" # replace with organization, grant and thanks.
        self.parent = parent

#
# qHelloPythonWidget
#

class BlenderLinkWidget:
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

    def setup(self):
        # Instantiate and connect widgets ...

        # Collapsible button
        sampleCollapsibleButton = ctk.ctkCollapsibleButton()
        sampleCollapsibleButton.text = "A collapsible button"
        self.layout.addWidget(sampleCollapsibleButton)

        # Layout within the sample collapsible button
        sampleFormLayout = qt.QFormLayout(sampleCollapsibleButton)

        # HelloWorld button
        helloWorldButton = qt.QPushButton("Import Blender")
        helloWorldButton.toolTip = "Print 'Hello world' in standard ouput."
        sampleFormLayout.addWidget(helloWorldButton)
        helloWorldButton.connect('clicked(bool)', self.onHelloWorldButtonClicked)
    
        # Add vertical spacer
        self.layout.addStretch(1)

        # Set local var as instance attribute
        self.helloWorldButton = helloWorldButton

    def onHelloWorldButtonClicked(self):
        #find the temp directory
        self_dir = os.path.dirname(os.path.abspath(__file__))
        tmp_dir = os.path.join(self_dir, "tmp")
        
        print(tmp_dir)
        
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
            else:
                print(name + ' model exists in scene already')
            
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

