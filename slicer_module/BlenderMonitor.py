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
import SurfaceToolbox
#import time

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
        parent.title = "linkSlicerBlender"
        parent.categories = ["Dentistry"]
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

    def onaddModelButtonToggled(self): #, select = None):
        for model in self.SlicerSelectedModelsList:
            if model[0] == None and model[2] == "NEW":
                return
        # https://python.hotexamples.com/examples/slicer/-/qMRMLNodeComboBox/python-qmrmlnodecombobox-function-examples.html
        modelNodeSelector = slicer.qMRMLNodeComboBox()
        modelNodeSelector.objectName = 'modelNodeSelector'
        modelNodeSelector.toolTip = "Select a model."
        modelNodeSelector.nodeTypes = ['vtkMRMLModelNode']
        modelNodeSelector.noneEnabled = True
        modelNodeSelector.addEnabled = True
        modelNodeSelector.removeEnabled = True
        #if select is not None:
        #    modelNodeSelector.currentNodeID = select
        modelNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.obj_check_send)
        self.sampleFormLayout.addRow(modelNodeSelector)

        self.parent.connect('mrmlSceneChanged(vtkMRMLScene*)', modelNodeSelector, 'setMRMLScene(vtkMRMLScene*)')
        modelNodeSelector.setMRMLScene(slicer.mrmlScene)
        
        self.SlicerSelectedModelsList.append([None , modelNodeSelector, "NEW"])
        #print(self.SlicerSelectedModelsList)

    def update_scene(self, xml):
        if not self.watching: return

        try: #any better ideas??
            tree = ET.ElementTree(ET.fromstring(xml))
        except:
            return
        x_scene = tree.getroot()
        
        s_scene = slicer.mrmlScene
        #scene = slicer.mrmlScene
        for b_ob in x_scene:
            #get the name of blender object
            name = b_ob.get('name')
                    
            
            xml_mx = b_ob.find('matrix')
            try:
                slicer_model = slicer.util.getNode(name)
            except slicer.util.MRMLNodeNotFoundException:
                slicer_model = None
                return
            
            #if not slicer_model:
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

            #update color
            if b_ob.find("material"):
                mat_color = b_ob.find('material')
                slicer_model.GetDisplayNode().SetColor(float(mat_color.find('r').text), float(mat_color.find('g').text), float(mat_color.find('b').text))

            #permanently apply transform - does not seem to work in live mode
            #logic = slicer.vtkSlicerTransformLogic()
            #logic.hardenTransform(slicer_model)

            #disp_node = slicer_model.GetDisplayNode()
            #disp_node.SetSliceIntersectionVisibility(True)
            #disp_node.SetSliceIntersectionThickness(2)
            
    def obj_check_handle(self, data):
        status, obj_name = data.split("_BREAK_")
        if status == "MISSING":
            self.send_model_to_blender(slicer.util.getNode(obj_name))
        elif status == "NOT LINKED":
            self.sock.send_data("CHECK", "LINK_BREAK_" + obj_name)
            #self.onaddModelButtonToggled()
        elif status == "LINKED":
            #slicer.util.confirmOkCancelDisplay("Object already linked.", "linkSlicerBlender Info:")
            pass
        elif status == "UNLINK":
            for model in self.SlicerSelectedModelsList:
                if model[0] == obj_name:
                    model[1].deleteLater()
                    self.SlicerSelectedModelsList.remove(model)

        elif status == "STATUS":
            try:
                slicer.util.getNode(obj_name)
                self.sock.send_data("CHECK", "LINK_BREAK_" + obj_name)
            except slicer.util.MRMLNodeNotFoundException:
                self.sock.send_data("CHECK", "MISSING_BREAK_" + obj_name)
        elif status == "STATUS_MULTIPLE":
            obj_name = obj_name.split(",")
            #print(obj_name)
            missing_objs = ""
            unlinked_objs = ""
            for obj in obj_name:
                try:
                    slicer.util.getNode(obj)
                    unlinked_objs = unlinked_objs + obj + ","
                except slicer.util.MRMLNodeNotFoundException:
                    missing_objs = missing_objs + obj + ","
            if not unlinked_objs == "" and missing_objs == "":
                self.sock.send_data("CHECK", "LINK_MULTIPLE_BREAK_" + unlinked_objs[:-1])
            elif not missing_objs == "" and unlinked_objs == "":
                self.sock.send_data("CHECK", "MISSING_MULTIPLE_BREAK_" + missing_objs[:-1])
            elif not missing_objs == "" and not unlinked_objs == "":
                self.sock.send_data("CHECK", "LINK+MISSING_MULTIPLE_BREAK_" + unlinked_objs[:-1] + ";" + missing_objs[:-1])

    def obj_check_send(self, modelNodeSelectorObj):
        #modelNode = modelNodeSelectorObj
        if modelNodeSelectorObj is not None:
            for model in self.SlicerSelectedModelsList:
                if model[0] == None and model[2] == "NEW":
                    self.SlicerSelectedModelsList[self.SlicerSelectedModelsList.index(model)][0] = modelNodeSelectorObj.GetName()
                    self.SlicerSelectedModelsList[self.SlicerSelectedModelsList.index(model)][2] = ""

            #slicer.util.confirmOkCancelDisplay("Checking object.", "linkSlicerBlender Info:")

            model_name = modelNodeSelectorObj.GetName()
            self.sock.send_data("CHECK", "STATUS_BREAK_" + model_name)
        else:
            for model in self.SlicerSelectedModelsList:
                if model[1].currentNode() == None and model[0] is not None:
                    self.sock.send_data("CHECK", "UNLINK_BREAK_" + model[0])
                    model[1].deleteLater()
                    self.SlicerSelectedModelsList.remove(model)
                    print(self.SlicerSelectedModelsList)
                    return

    def delete_model(self, obj_name):
        obj_name = obj_name.split(",")
        for model in self.SlicerSelectedModelsList:
            if model[0] in obj_name:
                model[1].deleteLater()
                self.SlicerSelectedModelsList.remove(model)
        for model in obj_name:
            try: slicer.mrmlScene.RemoveNode(slicer.util.getNode(model))
            except: pass

    def send_model_to_blender(self, modelNodeSelector):
        if not self.SlicerSelectedModelsList == []:
            modelNode = modelNodeSelector
            if len(slicer.util.arrayFromModelPoints(modelNode).tolist()) > 300000: #this can be fine tuned, lower for speed, 300,000 is optimal for geo preserve
                #print(len(slicer.util.arrayFromModelPoints(modelNode).tolist()))
                SFT_logic = SurfaceToolbox.SurfaceToolboxLogic()
                class state(object):
                    processValue = ""
                    parameterNode = SFT_logic.getParameterNode()
                    inputParamFile = ""
                    outputParamFile = ""
                    inputModelNode = modelNode
                    outputModelNode = modelNode
                    decimation = True
                    reduction = 0.95
                    boundaryDeletion = True
                    smoothing = True
                    smoothingMethod = "Laplace"
                    laplaceIterations = 300
                    laplaceRelaxation = 0.5
                    taubinIterations = 30
                    taubinPassBand = 0.1
                    boundarySmoothing = True
                    normals = False
                    flipNormals = False
                    autoOrientNormals = False
                    mirror = False
                    mirrorX = False
                    mirrorY = False
                    mirrorZ = False
                    splitting = False
                    featureAngle = 30.0
                    cleaner = True
                    fillHoles = True
                    fillHolesSize = 500.0
                    connectivity = True
                    scale = False
                    scaleX = 0.5
                    scaleY = 0.5
                    scaleZ = 0.5
                    translate = False
                    transX = 0
                    transY = 0
                    transZ = 0
                    relax = True
                    relaxIterations = 0.95
                    border = False
                    origin = False
                
                def updateProcess(value):
                    """Display changing process value"""
                    return

                
                result = SFT_logic.applyFilters(state, updateProcess)
                slicer.app.processEvents()
            #.currentNode()
            #print(len(slicer.util.arrayFromModelPoints(modelNode).tolist()))
            modelNode.CreateDefaultDisplayNodes()
            model_points = str(slicer.util.arrayFromModelPoints(modelNode).tolist())
            model_polys = str(self.arrayFromModelPolys(modelNode).tolist())
            packet = "%s_POLYS_%s_XML_DATA_%s"%(model_points, model_polys, tostring(self.build_xml_scene(modelNode.GetName())).decode())
            #print(model_polys)
            #print(packet)
            #slicer.util.confirmOkCancelDisplay("Sending object to Blender.", "linkSlicerBlender Info:")

            self.sock.send_data("OBJ", packet)

    def arrayFromModelPolys(self, modelNode):
        """Return point positions of a model node as numpy array.
        Point coordinates can be modified by modifying the numpy array.
        After all modifications has been completed, call :py:meth:`arrayFromModelPointsModified`.
        .. warning:: Important: memory area of the returned array is managed by VTK,
            therefore values in the array may be changed, but the array must not be reallocated.
            See :py:meth:`arrayFromVolume` for details.
        """
        #import vtk.util.numpy_support
        pointData = modelNode.GetPolyData().GetPolys().GetData()
        narray = vtk.util.numpy_support.vtk_to_numpy(pointData)
        return narray

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

    def build_xml_scene(self, nodeName):
        '''
        obs - list of slicer objects
        file - filepath to write the xml
        builds the XML scene of all object in self.SlicerSelectedModelsList
        '''
            
        x_scene = Element('scene')

        s_scene = slicer.mrmlScene
        if slicer.util.getNode(nodeName) is not None:
            model = slicer.util.getNode(nodeName)
            try:
                transform = slicer.util.getNode(model.GetName()+'_trans')
            except slicer.util.MRMLNodeNotFoundException:
                transform = None
                
            if not transform:
                transform = slicer.vtkMRMLTransformNode()
                transform.SetName(model.GetName()+'_trans')        
                s_scene.AddNode(transform)
            model.SetAndObserveTransformNodeID(transform.GetID())

            xob = SubElement(x_scene, 'b_object')
            xob.set('name', model.GetName())
            

            my_matrix = transform.GetMatrixTransformFromParent()
            xmlmx = self.matrix_to_xml_element(slicer.util.arrayFromVTKMatrix(my_matrix))
            xob.extend([xmlmx])
                        
        return x_scene

    def import_multiple(self, data):
        objects = data.split("_N_OBJ_")
        for obj in objects:
            self.import_obj_from_blender(obj)

    def import_obj_from_blender(self, data):
        #slicer.util.confirmOkCancelDisplay("Received object(s) from Blender.", "linkSlicerBlender Info:")
        def mkVtkIdList(it):
            vil = vtk.vtkIdList()
            for i in it:
                vil.InsertNextId(int(i))
            return vil
        #print(data)
        obj, xml = data.split("_XML_DATA_")
        obj_points, obj_polys = obj.split("_POLYS_")
        obj_points = eval(obj_points)
        obj_polys = eval(obj_polys)
        blender_faces = []
        offset = 0 #unflatten the list from blender
        while ( offset < len(obj_polys)):
            vertices_per_face = obj_polys[offset]
            offset += 1
            vertex_indices = obj_polys[offset : offset + vertices_per_face]
            blender_faces.append(vertex_indices)
            offset += vertices_per_face
        tree = ET.ElementTree(ET.fromstring(xml))
        x_scene = tree.getroot()

        mesh = vtk.vtkPolyData()
        points = vtk.vtkPoints()
        polys = vtk.vtkCellArray()
        #print(blender_faces)
        for i in range(len(obj_points)):
            points.InsertPoint(i, obj_points[i])
        for i in range(len(blender_faces)):
            polys.InsertNextCell(mkVtkIdList(blender_faces[i]))
        mesh.SetPoints(points)
        mesh.SetPolys(polys)

        # Create model node and add to scene
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
        modelNode.SetName(x_scene[0].get('name')) #only expecting one obj in the xml, since sent w/ OBJ together
        modelNode.SetAndObservePolyData(mesh)
        modelNode.CreateDefaultDisplayNodes()
        modelNode.GetDisplayNode().SetSliceIntersectionVisibility(True)
        modelNode.GetDisplayNode().SetSliceIntersectionThickness(2)

        #update object location in scene
        self.update_scene(xml)

        #self.SlicerSelectedModelsList.append([modelNodeSelector.currentNode().GetName(), modelNodeSelector, ""])

        #TODO: apply the incoming xml matrix data to the newly imported object right away, dont wait for the event from blender

    def onPlayButtonToggled(self, checked):
        if checked:
            self.watching = True
            self.playButton.text = "Stop"
            if self.sock == None:
                self.sock = asyncsock.SlicerComm.EchoClient(str(self.host_address.text), int(self.host_port.text), [("XML", self.update_scene), ("OBJ", self.import_obj_from_blender), ("OBJ_MULTIPLE", self.import_multiple), ("CHECK", self.obj_check_handle), ("DEL", self.delete_model)])
                #self.sock.send_data("TEST", 'bogus data from slicer!')
        else:
            self.watching = False
            self.playButton.text = "Start"
            self.sock.handle_close()
            self.sock = None
            
            #TODO
                
    def frameDelaySliderValueChanged(self, newValue):
        #print "frameDelaySliderValueChanged:", newValue
        self.timer.interval = newValue


