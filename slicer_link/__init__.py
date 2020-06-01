'''
Created on Mar 2, 2017

@author: Patrick, Georgi
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
    "author": "Patrick R. Moore, Georgi Talmazov",
    "version": (1, 1),
    "blender": (2, 80, 0),
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
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree, tostring, fromstring

#Blender
from bpy.types import Operator, AddonPreferences
from bpy.app.handlers import persistent
from io_mesh_ply import export_ply

#TCP sock lib
from .slicer_module import comm as asyncsock


def get_settings():
    addons = bpy.context.preferences.addons
    stack = inspect.stack()
    for entry in stack:
        folderpath = os.path.dirname(entry[1])
        foldername = os.path.basename(folderpath)
        if foldername not in {'lib','addons'} and foldername in addons: break
    else:
        assert False, 'could not find non-"lib" folder'
    settings = addons[foldername].preferences
    return settings
        
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
    r.text = str(round(mat.diffuse_color[0],4))
    g = SubElement(xml_mat, 'g')
    g.text = str(round(mat.diffuse_color[1],4))
    b = SubElement(xml_mat, 'b')
    b.text = str(round(mat.diffuse_color[2],4))
    
    return xml_mat

#a box to hold stuff in
class Box:
    pass

__m = Box()
__m.last_update = time.time()
__m.ob_names = []
__m.transform_cache = {}


def detect_transforms():
    if "SlicerLink" not in bpy.data.collections:
        return None
    
    changed = []
    sg = bpy.data.collections['SlicerLink']
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

def import_obj_from_slicer(data):
    #ShowMessageBox("Received object from Slicer.", "linkSlicerBlender Info:")

    obj, xml = data.split("_XML_DATA_")
    obj_points, obj_polys = obj.split("_POLYS_")
    obj_points = eval(obj_points)
    obj_polys = eval(obj_polys)
    blender_faces = []
    offset = 0 #unflatten the list from slicer
    while ( offset < len(obj_polys)):
        vertices_per_face = obj_polys[offset]
        offset += 1
        vertex_indices = obj_polys[offset : offset + vertices_per_face]
        blender_faces.append(vertex_indices)
        offset += vertices_per_face
    handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
    if "export_to_slicer" not in handlers:
        bpy.app.handlers.depsgraph_update_post.append(export_to_slicer) 
    if "SlicerLink" not in bpy.data.collections:
        sg = bpy.data.collections.new('SlicerLink')
    else:
        sg = bpy.data.collections['SlicerLink']
    #sg = bpy.data.collections['SlicerLink']
    tree = ElementTree(fromstring(xml))
    x_scene = tree.getroot()
    #we are expecting one object from slicer, so no need to iterate the XML object tree
    new_mesh = bpy.data.meshes.new(x_scene[0].get('name')+"_data")
    new_mesh.from_pydata(obj_points, [], blender_faces)
    new_mesh.update()
    new_object = bpy.data.objects.new(x_scene[0].get('name'), new_mesh)
    new_object.data = new_mesh
    scene = bpy.context.scene
    bpy.context.scene.collection.objects.link(new_object)

    sg.objects.link(new_object)
    write_ob_transforms_to_cache(sg.objects)
    #new_object.data.transform(matrix)
    #new_object.data.update()

def send_obj_to_slicer(objects = []):
    if asyncsock.socket_obj is not None:
        handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
        if "export_to_slicer" not in handlers:
            bpy.app.handlers.depsgraph_update_post.append(export_to_slicer) 
                        
        if "SlicerLink" not in bpy.data.collections:
            sg = bpy.data.collections.new('SlicerLink')
        else:
            sg = bpy.data.collections['SlicerLink']

        for ob in objects: #[TODO] object group managment 
            ob = bpy.data.objects[ob]
            #slicer does not like . in ob names
            if "." in ob.name:
                ob.name.replace(".","_")
            
            me = ob.to_mesh(preserve_all_data_layers=False, depsgraph=None)
            if not me:
                continue

            obj_verts = [list(v.co) for v in me.vertices]
            tot_verts = len(obj_verts[0])
            obj_poly = []
            for poly in me.polygons:
                obj_poly.append(tot_verts)
                for v in poly.vertices:
                    obj_poly.append(v)
            x_scene = build_xml_scene([ob])
        
            xml_str = tostring(x_scene).decode() #, encoding='unicode', method='xml')
            packet = "%s_POLYS_%s_XML_DATA_%s"%(obj_verts, obj_poly, xml_str)

            #ShowMessageBox("Sending object to Slicer.", "linkSlicerBlender Info:")

            asyncsock.socket_obj.sock_handler[0].send_data("OBJ", packet)
            ob.to_mesh_clear()

            if ob.name in sg.objects:
                continue
            else:
                sg.objects.link(ob)

        write_ob_transforms_to_cache(sg.objects)

def obj_check_handle(data):
    status, obj_name = data.split("_BREAK_")
    
    #ShowMessageBox(status, "linkSlicerBlender Info:")

    handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
    if "export_to_slicer" not in handlers:
        bpy.app.handlers.depsgraph_update_post.append(export_to_slicer) 
                    
    if "SlicerLink" not in bpy.data.collections:
        sg = bpy.data.collections.new('SlicerLink')
    else:
        sg = bpy.data.collections['SlicerLink']
    if status == "STATUS":
        link_col_found = obj_name in bpy.data.collections['SlicerLink'].objects
        b_obj_exist = obj_name in bpy.data.objects
        if link_col_found == True and b_obj_exist == True:
            asyncsock.socket_obj.sock_handler[0].send_data("CHECK", "LINKED_BREAK_" + obj_name)
        elif link_col_found == False and b_obj_exist == True:
            asyncsock.socket_obj.sock_handler[0].send_data("CHECK", "NOT LINKED_BREAK_" + obj_name)
        elif link_col_found == False and b_obj_exist == False:
            asyncsock.socket_obj.sock_handler[0].send_data("CHECK", "MISSING_BREAK_" + obj_name)
    elif status == "LINK":
        sg.objects.link(bpy.data.objects[obj_name])
        write_ob_transforms_to_cache(sg.objects)
    elif status == "MISSING":
        send_obj_to_slicer([obj_name])
    elif status == "UNLINK":
        sg.objects.unlink(bpy.data.objects[obj_name])
        write_ob_transforms_to_cache(sg.objects)

def obj_check_send():
    #ShowMessageBox("Checking object.", "linkSlicerBlender Info:")

    handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
    if "export_to_slicer" not in handlers:
        bpy.app.handlers.depsgraph_update_post.append(export_to_slicer) 
                    
    if "SlicerLink" not in bpy.data.collections:
        sg = bpy.data.collections.new('SlicerLink')
    else:
        sg = bpy.data.collections['SlicerLink']

    for ob in bpy.context.selected_objects:
        if ob.name not in bpy.data.collections['SlicerLink'].objects:
            asyncsock.socket_obj.sock_handler[0].send_data("CHECK", "STATUS_BREAK_" + ob.name)

@persistent
def export_to_slicer(scene):
    
    addons = bpy.context.preferences.addons
    settings = addons['slicer_link'].preferences
    
    #check for changes
    changed = detect_transforms()
    if changed == None: return  #TODO, more complex scene monitoring
    
    """
    #limit refresh rate to keep blender smooth    
    now = time.time()
    if now - __m.last_update < .2: return #TODO time limit
    __m.last_update = time.time()
    """
    
    #update the transform cache
    for ob_name in changed:
        if ob_name not in bpy.data.objects: continue
        __m.transform_cache[ob_name] = bpy.data.objects[ob_name].matrix_world.copy()
    
    #write an xml file with new info about objects
    obs = [bpy.data.objects.get(ob_name) for ob_name in changed if bpy.data.objects.get(ob_name)]
    x_scene = build_xml_scene(obs)
    xml_str = tostring(x_scene).decode()
    asyncsock.socket_obj.sock_handler[0].send_data("XML", xml_str)
            
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

class SelectedtoSlicerGroup(bpy.types.Operator):
    """
    Add selected objects to the SlicerLink group or
    replace the SlicerLing group with selected objects
    """
    bl_idname = "object.slicergroup"
    bl_label = "Slicer Group"
    
    def execute(self,context):
        
          
        if "SlicerLink" not in bpy.data.collections:
            sg = bpy.data.collections.new('SlicerLink')
        else:
            sg = bpy.data.collections['SlicerLink']
          
        if bpy.types.Scene.overwrite:
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

    
class StartSlicerLinkServer(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post/depsgraph_update_post (2.8) handler
    """
    bl_idname = "link_slicer.slicer_link_server_start"
    bl_label = "Server"
    
    def execute(self,context):
        if asyncsock.socket_obj == None:
            asyncsock.socket_obj = asyncsock.BlenderComm.EchoServer(context.scene.host_addr, int(context.scene.host_port), [("OBJ", import_obj_from_slicer), ("CHECK", obj_check_handle)])
            asyncsock.thread = asyncsock.BlenderComm.init_thread(asyncsock.BlenderComm.start)
            context.scene.socket_state = "SERVER"
            ShowMessageBox("Server started.", "linkSlicerBlender Info:")
        return {'FINISHED'}

class StartSlicerLinkClient(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post/depsgraph_update_post (2.8) handler
    """
    bl_idname = "link_slicer.slicer_link_client_start"
    bl_label = "Client"
    
    def execute(self,context):
        if asyncsock.socket_obj == None:
            asyncsock.socket_obj = asyncsock.BlenderComm.EchoClient(context.scene.host_addr, int(context.scene.host_port))
            asyncsock.thread = asyncsock.BlenderComm.init_thread(asyncsock.BlenderComm.start)
            context.scene.socket_state = "CLIENT"
            print("client started -> ")
        return {'FINISHED'}

class linkObjectsToSlicer(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post/depsgraph_update_post (2.8) handler
    """
    bl_idname = "link_slicer.link_objects_to_slicer"
    bl_label = "Link Object(s)"
    
    def execute(self,context):
        obj_check_send()
        return {'FINISHED'}

class unlinkObjectsFromSlicer(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post/depsgraph_update_post (2.8) handler
    """
    bl_idname = "link_slicer.unlink_objects_from_slicer"
    bl_label = "Unlink Object(s)"
    
    def execute(self,context):
        if "SlicerLink" not in bpy.data.collections:
            sg = bpy.data.collections.new('SlicerLink')
        else:
            sg = bpy.data.collections['SlicerLink']

        for ob in bpy.context.selected_objects:
            sg.objects.unlink(ob)
            asyncsock.socket_obj.sock_handler[0].send_data("CHECK", "UNLINK_BREAK_" + ob.name)
            write_ob_transforms_to_cache(sg.objects)
        return {'FINISHED'}

class deleteObjectsBoth(bpy.types.Operator):
    """
    Start updating slicer live by adding a scene_update_post/depsgraph_update_post (2.8) handler
    """
    bl_idname = "link_slicer.delete_objects_both"
    bl_label = "Delete Object(s)"
    
    def execute(self,context):
        if "SlicerLink" not in bpy.data.collections:
            sg = bpy.data.collections.new('SlicerLink')
        else:
            sg = bpy.data.collections['SlicerLink']
        for ob in bpy.context.selected_objects:
            asyncsock.socket_obj.sock_handler[0].send_data("DEL", ob.name)
            try: sg.objects.unlink(ob)
            except: pass
            ob.select_set(True)
            bpy.ops.object.delete()
            write_ob_transforms_to_cache(sg.objects)
        return {'FINISHED'}
            
    
class StopSlicerLink(bpy.types.Operator):
    """
    Stop updating slicer and remove the handler from scene_update_post
    """
    bl_idname = "link_slicer.slicer_link_stop"
    bl_label = "Slicer Link Stop"
    
    def execute(self,context):
        
        handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
        if "export_to_slicer" in handlers:
            bpy.app.handlers.depsgraph_update_post.remove(export_to_slicer) 
        
        addons = bpy.context.preferences.addons
        settings = addons['slicer_link'].preferences

        if context.scene.socket_state == "SERVER":
            asyncsock.socket_obj.stop_server(asyncsock.socket_obj)
            context.scene.socket_state = "NONE"
        elif context.scene.socket_state == "CLIENT":
            asyncsock.socket_obj.handle_close()
            context.scene.socket_state = "NONE"
        asyncsock.thread.join()
        print("thread joined")
        return {'FINISHED'}        


class SlicerLinkPanel(bpy.types.Panel):
    """Panel for Slicer LInk"""
    bl_label = "Slicer Link Panel"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = "Open Dental CAD"
    bl_context = ""

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        # Create a simple row.
        layout.label(text=" Configure:")

        row = layout.row()
        row.prop(context.scene, "host_addr")
        row = layout.row()
        row.prop(context.scene, "host_port")

        row = layout.row()
        if context.scene.socket_state == "NONE":
            row.label(text="Start Mode:")
            row.operator("link_slicer.slicer_link_server_start")
            row.operator("link_slicer.slicer_link_client_start")
        elif context.scene.socket_state == "SERVER" or context.scene.socket_state == "CLIENT":
            if context.scene.socket_state == "SERVER": row.label(text="Running: Server mode.")
            elif context.scene.socket_state == "CLIENT":row.label(text="Running: Client mode.")
            row = layout.row()
            row.operator("link_slicer.slicer_link_stop")
            
        if context.scene.socket_state == "SERVER" or context.scene.socket_state == "CLIENT":
            row = layout.row()
            row.label(text="Operators:")

            row = layout.row()
            row.operator("object.slicergroup")

            row = layout.row()
            row.operator("link_slicer.link_objects_to_slicer")

            row = layout.row()
            row.operator("link_slicer.unlink_objects_from_slicer")

            row = layout.row()
            row.operator("link_slicer.delete_objects_both")
        

        


        
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

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def register():
    #register host address, port input, state=NONE/CLIENT/SERVER
    bpy.types.Scene.host_addr = bpy.props.StringProperty(name = "Host", description = "Enter the host PORT the server to listen on OR client to connect to.", default = asyncsock.address[0])
    bpy.types.Scene.host_port = bpy.props.StringProperty(name = "Port", description = "Enter the host PORT the server to listen on OR client to connect to.", default = str(asyncsock.address[1]))
    bpy.types.Scene.socket_state = bpy.props.StringProperty(name="socket_state", default="NONE")

    bpy.types.Scene.overwrite = bpy.props.BoolProperty(name = "Overwrite", default = True, description = "If False, will add objects, if True, will replace entire group with selection")

    bpy.utils.register_class(SelectedtoSlicerGroup)
    bpy.utils.register_class(StopSlicerLink)
    bpy.utils.register_class(StartSlicerLinkServer)
    bpy.utils.register_class(StartSlicerLinkClient)
    bpy.utils.register_class(SlicerLinkPanel)
    bpy.utils.register_class(linkObjectsToSlicer)
    bpy.utils.register_class(unlinkObjectsFromSlicer)
    bpy.utils.register_class(deleteObjectsBoth)
    

def unregister():
    del bpy.types.Scene.host_addr
    del bpy.types.Scene.host_port
    del bpy.types.Scene.socket_state
    del bpy.types.Scene.overwrite
    bpy.utils.unregister_class(SelectedtoSlicerGroup)
    bpy.utils.unregister_class(SlicerLinkPanel)
    bpy.utils.unregister_class(linkObjectsToSlicer)
    bpy.utils.unregister_class(unlinkObjectsFromSlicer)
    bpy.utils.unregister_class(deleteObjectsBoth)    
    
    handlers = [hand.__name__ for hand in bpy.app.handlers.depsgraph_update_post]
    if "export_to_slicer" in handlers:
        bpy.app.handlers.depsgraph_update_post.remove(export_to_slicer)
    """
    handlers = [hand.__name__ for hand in bpy.app.handlers.load_post]
    if "cleanup_temp_dir" in handlers:
        bpy.app.handlers.load_post.remove(cleanup_temp_dir)
    """
    #bpy.utils.unregister_manual_map(SlicerXMLExport)
    #bpy.utils.unregister_manual_map(SlicerPLYExport)
    
if __name__ == "__main__":
    register()