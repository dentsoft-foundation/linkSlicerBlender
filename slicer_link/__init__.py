'''
Created on Mar 2, 2017

@author: Patrick
'''
'''
https://pymotw.com/2/xml/etree/ElementTree/create.html
https://docs.python.org/2/library/xml.etree.elementtree.html
https://www.na-mic.org/Wiki/index.php/AHM2012-Slicer-Python
https://www.slicer.org/wiki/Documentation/Nightly/ScriptRepository
https://gist.github.com/ungi/4b0bd3a109bd98de054c66cc1ec6cfab
http://stackoverflow.com/questions/6597552/mathematica-write-matrix-data-to-xml-read-matrix-data-from-xml

#handling updated status in Slicer and in Blender
http://stackoverflow.com/questions/1977362/how-to-create-module-wide-variables-in-python

#Panel List
http://blender.stackexchange.com/questions/14202/index-out-of-range-for-uilist-causes-panel-crash/14203#14203

'''
bl_info = {
    "name": "Blender Scene to Slicer",
    "author": "Patrick R. Moore",
    "version": (1, 0),
    "blender": (2, 78, 0),
    "location": "File > Export > Slicer (.xml)",
    "description": "Adds a new Mesh Object",
    "warning": "",
    "wiki_url": "",
    "category": "Import Export",
    }
#python
import os
import inspect
import time
import numpy as np

#Blender
import bpy

#XML
from xml.etree import ElementTree as ET
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree

#Blender
from bpy.types import Operator, AddonPreferences
from bpy.app.handlers import persistent
from io_mesh_ply import export_ply

def get_settings():
    addons = bpy.context.user_preferences.addons
    stack = inspect.stack()
    for entry in stack:
        folderpath = os.path.dirname(entry[1])
        foldername = os.path.basename(folderpath)
        if foldername not in {'lib','addons'} and foldername in addons: break
    else:
        assert False, 'could not find non-"lib" folder'
    settings = addons[foldername].preferences
    return settings

#Preferences
class SlicerAddonPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__
    self_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_dir = os.path.join(self_dir, "slicer_module","tmp")
    tmpdir = bpy.props.StringProperty(name = "Temp Folder", default = tmp_dir, subtype = 'DIR_PATH')
    
    def draw(self,context):
        
        layout = self.layout
        row = layout.row()
        row.prop(self, "tmpdir")
        
def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def matrix_to_xml_element(mx):
    nrow = len(mx.row)
    ncol = len(mx.row[0])
    
    xml_mx = Element('matrix')
    
    for i in range(0,nrow):
        xml_row = SubElement(xml_mx, 'row')
        for j in range(0,ncol):
            mx_entry = SubElement(xml_row, 'entry')
            mx_entry.text = str(mx[i][j])
            
    return xml_mx

def material_to_xml_element(mat):
    
    xml_mat = Element('material')

    r = SubElement(xml_mat, 'r')
    r.text = str(round(mat.diffuse_color.r,4))
    g = SubElement(xml_mat, 'g')
    g.text = str(round(mat.diffuse_color.g,4))
    b = SubElement(xml_mat, 'b')
    b.text = str(round(mat.diffuse_color.b,4))
    
    return xml_mat

#a box to hold stuff in
class Box:
    pass

__m = Box()
__m.last_update = time.time()
__m.ob_names = []
__m.transform_cache = {}


def detect_transforms():
    if "SlicerLink" not in bpy.data.groups:
        return None
    
    changed = []
    sg = bpy.data.groups['SlicerLink']
    for ob in sg.objects:
        if ob.name not in __m.transform_cache:
            changed += [ob.name]
            #
            #__m.transform_cache[ob.name] = ob.matrix_world.copy()
            
        elif not np.allclose(ob.matrix_world, __m.transform_cache[ob.name]):
            changed += [ob.name]
            #don't update until we know slicer has implemented previous changes
            #__m.transform_cache[ob.name] = ob.matrix_world.copy()
            
    if len(changed) == 0: return None
    return changed    

#when closing file, delete temp dir contents
@persistent
def cleanup_temp_dir(dummy):
    addons = bpy.context.user_preferences.addons
    settings = addons['slicer_link'].preferences
    #safety, need the directory to exist
    if not os.path.exists(settings.tmp_dir): return
    
    files = os.listdir(settings.tmp_dir)
    
    #cleanup everything
    for f in files:
        to_rem = os.path.join(settings.tmp_dir, f)
        os.remove(to_rem)
    
    #send a message to slicer that the scene has changed
    closed = os.path.join(settings.tmp_dir, 'closed.txt')
    close_file = open(closed,'wb')
    close_file.close()
    
    
@persistent
def export_to_slicer(scene):
    
    addons = bpy.context.user_preferences.addons
    settings = addons['slicer_link'].preferences
    
    #check for changes
    changed = detect_transforms()
    if changed == None: return  #TODO, more complex scene monitoring
    
    #safety, need the directory to exist
    if not os.path.exists(settings.tmp_dir): return
    
    #limit refresh rate to keep blender smooth    
    now = time.time()
    if now - __m.last_update < .2: return #TODO time limit
    __m.last_update = time.time()    
        
    update_file_name = os.path.join(settings.tmp_dir, 'update.txt')
    
    #don't update unless slier has read previous changes
    if os.path.exists(update_file_name):
        print('slicer has not updated changes, cache changes?')
        return
    
    #update the transform cache
    for ob_name in changed:
        if ob_name not in bpy.data.objects: continue
        __m.transform_cache[ob_name] = bpy.data.objects[ob_name].matrix_world.copy()
    
    #write an xml file with new info about objects
    obs = [bpy.data.objects.get(ob_name) for ob_name in changed if bpy.data.objects.get(ob_name)]
    x_scene = build_xml_scene(obs)
    xml_file_name = os.path.join(settings.tmp_dir, "blend_to_slicer.xml")
    
    if not os.path.exists(xml_file_name):
        my_file = open(xml_file_name, 'xb')
    else:
        my_file = open(xml_file_name,'wb')
    
    ElementTree(x_scene).write(my_file)
    my_file.close()
    
    #send signal for slicer to update.  #TODO, send signal with socket
    new_file = open(update_file_name, mode='xb')
    new_file.write('Update Slicer please'.encode())
    new_file.close()            
            
def write_ob_transforms_to_cache(obs):
    __m.ob_names = []
    for ob in obs:
        __m.transform_cache[ob.name] = ob.matrix_world.copy()
        __m.ob_names += [ob.name]

def build_xml_scene(obs):
    '''
    obs - list of blender objects
    file - filepath to write the xml
    '''
        
    x_scene = Element('scene')
    
    for ob in obs:
        xob = SubElement(x_scene, 'b_object')
        xob.set('name', ob.name)
        
        xmlmx = matrix_to_xml_element(ob.matrix_world)
        xob.extend([xmlmx])
        
        if len(ob.material_slots):
            mat = ob.material_slots[0].material
            xmlmat = material_to_xml_element(mat)
            xob.extend([xmlmat])
    
    return x_scene
    '''    
    if not os.path.exists(file_path):
        my_file = open(file_path, 'xb')
    else:
        my_file = open(file_path,'wb')
    
    ElementTree(x_scene).write(my_file)
    my_file.close()
    '''
                 
class SelectedtoSlicerGroup(bpy.types.Operator):
    """
    Add selected objects to the SlicerLink group or
    replace the SlicerLing group with selected objects
    """
    bl_idname = "object.slicergroup"
    bl_label = "Slicer Group"
    
    overwrite = bpy.props.BoolProperty(name = "Overwrite", default = True, description = "If False, will add objects, if True, will replace entire group with selection")
    
    def execute(self,context):
        
          
        if "SlicerLink" not in bpy.data.groups:
            sg = bpy.data.groups.new('SlicerLink')
        else:
            sg = bpy.data.groups['SlicerLink']
          
        if self.overwrite:
            for ob in sg.objects:
                sg.objects.unlink(ob)
                
        for ob in context.selected_objects: #[TODO] object group managments
            #slicer does not like . in ob names
            if ob.name in sg.objects:
                continue
            else:
                sg.objects.link(ob)
        
        #I had to split the fn off because I could not reference
        #__m within the operator class, it seemed to think it
        #had to belong to the SlicerToGroup class.
        write_ob_transforms_to_cache(sg.objects)
        
        return {'FINISHED'}
    
    
class SlicerPLYExport(bpy.types.Operator):
    """
    export selected objects mesh in local coords to
    stanford PLY
    """
    bl_idname = "export.slicerply"
    bl_label = "Export Slicer Ply"
    
    overwrite = bpy.props.BoolProperty(name = "Overwrite", default = True)
    def execute(self,context):
        #check tmp dir for exchange file
        temp_dir = get_settings().tmpdir
        if temp_dir == '' or not os.path.isdir(temp_dir):
            self.report({'ERROR'}, 'Temp directory doesnt exist, set temp directory in addon preferences')
            return {'CANCELLED'}
        
        #clean old ply files from tmp dir
        for parent, dirnames, filenames in os.walk(temp_dir):
            for fn in filenames:
                if fn.lower().endswith('.ply'):
                    os.remove(os.path.join(parent, fn))
            
        for ob in context.selected_objects: #[TODO] object group managments
            #slicer does not like . in ob names
            if "." in ob.name:
                ob.name.replace(".","_")
                
            temp_file = os.path.join(temp_dir, ob.name + ".ply")
            if os.path.exists(temp_file):
                print('overwriting')
            
            me = ob.to_mesh(context.scene, True, 'PREVIEW')
            if not me:
                continue
            
            ret = export_ply.save_mesh(temp_file, me,
                    use_normals=False,
                    use_uv_coords=False,
                    use_colors=False,
                    )
            bpy.data.meshes.remove(me)
        
            
        return {'FINISHED'}
            
class SlicerXMLExport(bpy.types.Operator):
    """
    Export to the scene object names and transforms to XML
    """
    bl_idname = "export.slicerxml"
    bl_label = "Export Slicer XML"
    
    def execute(self,context):
        
        x_scene = Element('scene')
        
        for ob in context.scene.objects:
            xob = SubElement(x_scene, 'b_object')
            xob.set('name', ob.name)
            
            xmlmx = matrix_to_xml_element(ob.matrix_world)
            xob.extend([xmlmx])
            
            if len(ob.material_slots):
                mat = ob.material_slots[0].material
                xmlmat = material_to_xml_element(mat)
                xob.extend([xmlmat])
                print(prettify(xmlmat))
                
        #check tmp dir for exchange file
        temp_dir = get_settings().tmpdir
        if temp_dir == '' or not os.path.isdir(temp_dir):
            self.report({'ERROR'}, 'Temp directory doesnt exist, set temp directory in addon preferences')
            return {'CANCELLED'}
        temp_file = os.path.join(temp_dir,"blend_to_slicer.xml")
        if not os.path.exists(temp_file):
            my_file = open(temp_file, 'xb')
        else:
            my_file = open(temp_file,'wb')
        
        ElementTree(x_scene).write(my_file)
        my_file.close()
        
        return {'FINISHED'}
    
class StartSlicerLink(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post handler
    """
    bl_idname = "scene.slicer_link_start"
    bl_label = "Slicer Link Start"
    
    def execute(self,context):
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.scene_update_post]
        
        if "export_to_slicer" not in handlers:
            bpy.app.handlers.scene_update_post.append(export_to_slicer) 
        
        addons = bpy.context.user_preferences.addons
        settings = addons['slicer_link'].preferences
        #safety, need the directory to exist
        if not os.path.exists(settings.tmp_dir): return {'FINISHED'} #TODO Error no tmp directory
        
        if 'closed.txt' in os.listdir(settings.tmp_dir):
            #send a message to slicer that the scene has changed
            closed = os.path.join(settings.tmp_dir, 'closed.txt')
            os.remove(closed)
        
        if "SlicerLink" not in bpy.data.groups: return {'FINISHED'} #TODO Error no group
        sg = bpy.data.groups['SlicerLink']
        for ob in sg.objects: #[TODO] object group managment
            #slicer does not like . in ob names
            if "." in ob.name:
                ob.name.replace(".","_")
                
            temp_file = os.path.join(settings.tmp_dir, ob.name + ".ply")
            if os.path.exists(temp_file):
                print('overwriting')
            
            me = ob.to_mesh(context.scene, True, 'PREVIEW')
            if not me:
                continue
            
            ret = export_ply.save_mesh(temp_file, me,
                    use_normals=False,
                    use_uv_coords=False,
                    use_colors=False,
                    )
            bpy.data.meshes.remove(me)
        
        #write an xml file with new info about objects
        obs = [ob for ob in sg.objects]
        x_scene = build_xml_scene(obs)
        xml_file_name = os.path.join(settings.tmp_dir, "blend_to_slicer.xml")
        
        if not os.path.exists(xml_file_name):
            my_file = open(xml_file_name, 'xb')
        else:
            my_file = open(xml_file_name,'wb')
        
        ElementTree(x_scene).write(my_file)
        my_file.close()
        
        #send signal for slicer to update.  #TODO, send signal with socket
        update_file_name = os.path.join(settings.tmp_dir, 'update.txt')
        new_file = open(update_file_name, mode='xb')
        new_file.write('Update Slicer please'.encode())
        new_file.close() 
        return {'FINISHED'}
    
class StopSlicerLink(bpy.types.Operator):
    """
    Stop updating slicer and remove the handler from scene_update_post
    """
    bl_idname = "scene.slicer_link_stop"
    bl_label = "Slicer Link Stop"
    
    def execute(self,context):
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.scene_update_post]
        if "export_to_slicer" in handlers:
            bpy.app.handlers.scene_update_post.remove(export_to_slicer) 
        
        addons = bpy.context.user_preferences.addons
        settings = addons['slicer_link'].preferences
        #send a message to slicer that the scene has changed
        closed = os.path.join(settings.tmp_dir, 'closed.txt')
        close_file = open(closed,'wb')
        close_file.close()
        
        #clean out temp files?  No just pause the link?
        update = os.path.join(settings.tmp_dir, 'update.txt')
        if os.path.exists(update):
            os.remove(update)
            
        return {'FINISHED'}        


class SlicerLinkPanel(bpy.types.Panel):
    """Panel for Slicer LInk"""
    bl_label = "Slicer Link Panel"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'TOOLS'
    bl_category = "Open Dental CAD"
    bl_context = ""

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        # Create a simple row.
        layout.label(text=" Simple Row:")

        row = layout.row()
        row.operator("object.slicergroup")
        
        row = layout.row()
        row.operator("scene.slicer_link_start")
        
        row = layout.row()
        row.operator("scene.slicer_link_stop")
        
        '''
        # Create an row where the buttons are aligned to each other.
        layout.label(text=" Aligned Row:")

        row = layout.row(align=True)
        row.prop(scene, "frame_start")
        row.prop(scene, "frame_end")

        # Create two columns, by using a split layout.
        split = layout.split()

        # First column
        col = split.column()
        col.label(text="Column One:")
        col.prop(scene, "frame_end")
        col.prop(scene, "frame_start")

        # Second column, aligned
        col = split.column(align=True)
        col.label(text="Column Two:")
        col.prop(scene, "frame_start")
        col.prop(scene, "frame_end")

        # Big render button
        layout.label(text="Big Button:")
        row = layout.row()
        row.scale_y = 3.0
        row.operator("render.render")

        # Different sizes in a row
        layout.label(text="Different button sizes:")
        row = layout.row(align=True)
        row.operator("render.render")

        sub = row.row()
        sub.scale_x = 2.0
        sub.operator("render.render")

        row.operator("render.render")
        '''

def register():
    bpy.utils.register_class(SlicerAddonPreferences)
    bpy.utils.register_class(SlicerXMLExport)
    bpy.utils.register_class(SlicerPLYExport)
    bpy.utils.register_class(SelectedtoSlicerGroup)
    bpy.utils.register_class(StopSlicerLink)
    bpy.utils.register_class(StartSlicerLink)
    bpy.utils.register_class(SlicerLinkPanel)
    
    bpy.app.handlers.load_post.append(cleanup_temp_dir)
    #bpy.utils.register_manual_map(SlicerXMLExport)
    #bpy.utils.register_manual_map(SlicerPLYExport)
    

def unregister():
    bpy.utils.unregister_class(SlicerXMLExport)
    bpy.utils.unregister_class(SlicerXMLExport)
    bpy.utils.unregister_class(SlicerPLYExport)
    bpy.utils.unregister_class(SelectedtoSlicerGroup)
    bpy.utils.unregister_class(SlicerLinkPanel)
    
    handlers = [hand.__name__ for hand in bpy.app.handlers.scene_update_post]
    if "export_to_slicer" in handlers:
        bpy.app.handlers.scene_update_post.remove(export_to_slicer) 
    handlers = [hand.__name__ for hand in bpy.app.handlers.load_post]
    if "cleanup_temp_dir" in handlers:
        bpy.app.handlers.load_post.remove(cleanup_temp_dir)
    #bpy.utils.unregister_manual_map(SlicerXMLExport)
    #bpy.utils.unregister_manual_map(SlicerPLYExport)
    
if __name__ == "__main__":
    register()