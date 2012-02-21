# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
from sets import Set
from tools.translate import _
import time

class external_referential_category(osv.osv):
    _name = 'external.referential.category'
    _description = 'External Referential Category (Ex: e-commerce, crm, warehouse)'
    
    _columns = {
        'name': fields.char('Name', size=64, required=True), #dont allow creation of type from frontend
        'type_ids': fields.one2many('external.referential.type', 'categ_id', 'Types', required=True)
    }
    
external_referential_category()

class external_referential_type(osv.osv):
    _name = 'external.referential.type'
    _description = 'External Referential Type (Ex.Magento,Spree)'
    
    _columns = {
        'name': fields.char('Name', size=64, required=True), #dont allow creation of type from frontend
        'categ_id': fields.many2one('external.referential.category', 'Category'),
        'version_ids': fields.one2many('external.referential.version', 'type_id', 'Versions', required=True)
    }
    
external_referential_type()

class external_referential_version(osv.osv):
    _name = 'external.referential.version'
    _description = 'External Referential Version (Ex: v1.5.0.0 +, v1.3.2.4 +)'
    _rec_name = 'full_name'    

    def _get_full_name(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for version in self.read(cr, uid, ids, ['name', 'type_id'], context=context):
            res[version['id']] = '%s %s'%(version['type_id'][1], version['name'])
        return res

    _columns = {
        'full_name': fields.function(_get_full_name, store=True, type='char', size=64, string='Full Name'),
        'name': fields.char('name', size=64, required=True),
        'type_id': fields.many2one('external.referential.type', 'Type', required=True),
    }
    
external_referential_type()

class external_mapping_template(osv.osv):
    _name = "external.mapping.template"
    _description = "The source mapping records"
    _rec_name = 'model'
    
    _columns = {
        'version_id':fields.many2one('external.referential.version', 'External Referential Version', ondelete='cascade'),
        'model_id': fields.many2one('ir.model', 'OpenERP Model', required=True, ondelete='cascade'),
        'model':fields.related('model_id', 'model', type='char', string='Model Name'),
        'external_list_method': fields.char('List Method', size=64),
        'external_get_method': fields.char('Get Method', size=64),
        'external_update_method': fields.char('Update Method', size=64),
        'external_create_method': fields.char('Create Method', size=64),
        'external_delete_method': fields.char('Delete Method', size=64),
        'external_key_name':fields.char('External field used as key', size=64),
        'external_resource_name':fields.char('External Resource Name', size=64),
                }
external_mapping_template()

class external_mappinglines_template(osv.osv):
    _name = 'external.mappinglines.template'
    _description = 'The source mapping line records'
    _rec_name = 'name_function'
    
    def _name_get_fnc(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for mapping_line in self.browse(cr, uid, ids, context):
            res[mapping_line.id] = mapping_line.field_id or mapping_line.external_field
        return res

    _columns = {
        'name_function': fields.function(_name_get_fnc, type="char", string='Full Name'),
        'version_id':fields.many2one('external.referential.version', 'External Referential Version', ondelete='cascade'),
        'field_id': fields.many2one('ir.model.fields', 'OpenERP Field', ondelete='cascade'),
        'model_id': fields.many2one('ir.model', 'OpenERP Model', ondelete='cascade'),
        'model':fields.related('model_id', 'model', type='char', string='Model Name'),
        'external_field': fields.char('External Field', size=32),
        'type': fields.selection([('in_out', 'External <-> OpenERP'), ('in', 'External -> OpenERP'), ('out', 'External <- OpenERP')], 'Type'),
        'evaluation_type': fields.selection([('function', 'Function'), ('sub-mapping','Sub Mapping Line'), ('direct', 'Direct Mapping')], 'Evalution Type', required=True),
        'external_type': fields.selection([('o2m', 'one2many'), ('unicode', 'String'), ('bool', 'Boolean'), ('int', 'Integer'), ('float', 'Float'), ('list', 'List'), ('dict', 'Dictionnary')], 'External Type', required=True),
        'in_function': fields.text('Import in OpenERP Mapping Python Function'),
        'out_function': fields.text('Export from OpenERP Mapping Python Function'),
        'child_mapping_id': fields.many2one('external.mapping.template', 'Child Mapping', ondelete='cascade',
            help=('This give you the possibility to import data with a structure of Parent/child'
                'For example when you import a sale order, the sale order is the parent of the sale order line'
                'In this case you have to select the child mapping in order to convert the data'
                )
            ),
        }

external_mappinglines_template()

class external_referential(osv.osv):
    _name = 'external.referential'
    _description = 'External Referential'

    def external_connection(self, cr, uid, referential, DEBUG=False, context=None):
        """Should be overridden to provide valid external referential connection"""
        return False

    def import_referentials(self, cr, uid, ids, context=None):
        self.import_resources(cr, uid, ids, 'external.referential', context=context)
        return True

    def refresh_mapping(self, cr, uid, ids, context={}):
        #This function will reinstate mapping & mapping_lines for registered objects
        for id in ids:
            ext_ref = self.browse(cr, uid, id)
            mappings_obj = self.pool.get('external.mapping')
            mapping_line_obj = self.pool.get('external.mapping.line')
            mapping_tmpl_obj = self.pool.get('external.mapping.template')
            
            #Delete Existing mappings if any
            cr.execute("""select id from (select distinct external_mapping_line.id, external_mapping.model_id
                            from (external_mapping_line join external_mapping on external_mapping.id = external_mapping_line.mapping_id)
                            join external_mappinglines_template on (external_mappinglines_template.external_field = external_mapping_line.external_field
                            and external_mappinglines_template.model_id = external_mapping.model_id)
                            where external_mapping.referential_id=%s order by external_mapping_line.id) as tmp;""", (id,))
            existing_mapping_ids = cr.fetchall()
            if existing_mapping_ids:
                mapping_line_obj.unlink(cr, uid, [tuple[0] for tuple in existing_mapping_ids])

            link_parent_child_mapping = []
            template_mapping_id_to_mapping_id = {}
            #Fetch mapping lines now
            mapping_src_ids = self.pool.get('external.mapping.template').search(cr, uid, [('version_id', '=', ext_ref.version_id.id)])
            for each_mapping_rec in self.pool.get('external.mapping.template').read(cr, uid, mapping_src_ids, []):
                existing_ids = mappings_obj.search(cr, uid, [('referential_id', '=', id), ('model_id', '=', each_mapping_rec['model_id'][0] or False)])
                if len(existing_ids) == 0:
                    vals = {
                                    'referential_id': id,
                                    'model_id': each_mapping_rec['model_id'][0] or False,
                                    'external_list_method': each_mapping_rec['external_list_method'],
                                    'external_get_method': each_mapping_rec['external_get_method'],
                                    'external_update_method': each_mapping_rec['external_update_method'],
                                    'external_create_method': each_mapping_rec['external_create_method'],
                                    'external_delete_method': each_mapping_rec['external_delete_method'],
                                    'external_key_name': each_mapping_rec['external_key_name'],
                                    'external_resource_name': each_mapping_rec['external_resource_name'],
                                                }
                    mapping_id = mappings_obj.create(cr, uid, vals)
                else:
                    mapping_id = existing_ids[0]
                    data = self.pool.get('ir.model').read(cr, uid, [each_mapping_rec['model_id'][0]], ['model', 'name'], context)[0]
                    model = data['model']
                    model_name = data['name']
                    self.pool.get('external.mapping').create_external_link(cr, uid, model, model_name)

                template_mapping_id_to_mapping_id[each_mapping_rec['id']] = mapping_id

                #Now create mapping lines of the created mapping model
                mapping_lines_src_ids = self.pool.get('external.mappinglines.template').search(cr, uid, [('version_id', '=', ext_ref.version_id.id), ('model_id', '=', each_mapping_rec['model_id'][0])])
                for each_mapping_line_rec in  self.pool.get('external.mappinglines.template').read(cr, uid, mapping_lines_src_ids, []):
                    vals = {
                        'external_field': each_mapping_line_rec['external_field'],
                        'mapping_id': mapping_id,
                        'type': each_mapping_line_rec['type'],
                        'evaluation_type': each_mapping_line_rec['evaluation_type'],
                        'external_type': each_mapping_line_rec['external_type'],
                        'in_function': each_mapping_line_rec['in_function'],
                        'out_function': each_mapping_line_rec['out_function'],
                        'field_id': each_mapping_line_rec['field_id'] and each_mapping_line_rec['field_id'][0] or False,
                        'active':True,
                        }
                    mapping_line_id = mapping_line_obj.create(cr, uid, vals)
                    if each_mapping_line_rec['child_mapping_id']:
                        link_parent_child_mapping.append([mapping_line_id, each_mapping_line_rec['child_mapping_id'][0]])

            #Now link the sub-mapping to the corresponding child
            for mapping_line_id, mapping_tmpl_id in link_parent_child_mapping:
                mapping_id = template_mapping_id_to_mapping_id[mapping_tmpl_id]
                mapping_line_obj.write(cr, uid, mapping_line_id, {'child_mapping_id': mapping_id}, context=context)
        return True
            
                
    _columns = {
        'name': fields.char('Name', size=32, required=True),
        'type_id': fields.related('version_id', 'type_id', type='many2one', relation='external.referential.type', string='External Type'),
        'categ_id': fields.related('type_id', 'categ_id', type='many2one', relation='external.referential.category', string='External Category'),
        'categ_name': fields.related('categ_id', 'name', type='char', string='External Category Name'),
        'version_id': fields.many2one('external.referential.version', 'Referential Version', required=True),
        'location': fields.char('Location', size=200, required=True),
        'apiusername': fields.char('User Name', size=64),
        'apipass': fields.char('Password', size=64),
        'mapping_ids': fields.one2many('external.mapping', 'referential_id', 'Mappings'),
        'create_date': fields.datetime('Creation Date', readonly=True, help="Date on which external referential is created."),
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Referential names must be unique !')
    ]

    def _test_dot_in_name(self, cr, uid, ids, context=None):
        for referential in self.browse(cr, uid, ids):
            if '.' in referential.name:
                return False
        return True

    # Method to export external referential type
    def build_external_ref_type(self, cr, uid, ids, context={}):
        csv_file = "\"id\",\"name\",\"categ_id:id\"\n"
        referential = self.browse(cr, uid, ids)[0]
        print "referential: ",referential
        csv_file += "\""+referential.type_id.name+"_"+time.strftime('%Y_%m')+"\","
        csv_file += "\""+referential.type_id.name+"\","
        csv_file += "\""+referential.type_id.categ_id.get_external_id(context=context)[referential.type_id.categ_id.id]+"\""
        raise osv.except_osv(_('external_referential_type.csv'), _(csv_file))
        return True

    # Method to export external referential version
    def build_external_ref_version(self, cr, uid, ids, context={}):
        csv_file = "\"type_id:id\",\"id\",\"name\"\n"
        referential = self.browse(cr, uid, ids)[0]
        csv_file += "\""+referential.type_id.get_external_id(context=context)[referential.type_id.id]+"\","
        csv_file += "\""+referential.version_id.name+"_"+time.strftime('%Y_%m')+"\","
        csv_file += "\""+referential.version_id.name+"\""
        raise osv.except_osv(_('external_referential_version.csv'), _(csv_file))
        return True

    # Method to export external referential type
    def build_external_mapping_template(self, cr, uid, ids, context={}):
        csv_file = "\"id\",\"version_id:id\",\"model_id:id\",\"external_list_method\",\"external_get_method\",\"external_update_method\",\"external_create_method\",\"external_delete_method\",\"external_key_name\",\"external_resource_name\"\n"
        referential = self.browse(cr, uid, ids)[0]
        for mapping in referential.mapping_ids:
            csv_file += "\""+referential.name+"_"+referential.version_id.name+"_"+mapping.model_id.name+"\","
            csv_file += "\""+referential.version_id.get_external_id(context=context)[referential.version_id.id]+"\","
            csv_file += "\""+mapping.model_id.get_external_id(context=context)[mapping.model_id.id]+"\","
            if mapping.external_list_method!=False:
                csv_file += "\""+mapping.external_list_method+"\","
            else:
                csv_file += "\"\","            
            if mapping.external_get_method!=False:
                csv_file += "\""+mapping.external_get_method+"\","
            else:
                csv_file += "\"\","
            if mapping.external_update_method!=False:
                csv_file += "\""+mapping.external_update_method+"\","
            else:
                csv_file += "\"\","
            if mapping.external_create_method!=False:
                csv_file += "\""+mapping.external_create_method+"\","
            else:
                csv_file += "\"\","
            if mapping.external_delete_method!=False:
                csv_file += "\""+mapping.external_delete_method+"\","
            else:
                csv_file += "\"\","
            if mapping.external_key_name!=False:
                csv_file += "\""+mapping.external_key_name+"\","
            else:
                csv_file += "\"\","
            if mapping.external_resource_name!=False:
                csv_file += "\""+mapping.external_resource_name+"\"\n"
            else:
                csv_file += "\"\"\n"
        raise osv.except_osv(_('external_referential_mapping_template.csv'), _(csv_file))
        return True

    _constraints = [
        (_test_dot_in_name, 'The name cannot contain a dot!', ['name']),
    ]
    
    #TODO warning on name change if mapping exist: Implemented in attrs
    
external_referential()

class external_mapping_line(osv.osv):
    _name = 'external.mapping.line'
    _description = 'Field Mapping'
    _rec_name = 'name_function'
    
    def _name_get_fnc(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for mapping_line in self.browse(cr, uid, ids, context):
            res[mapping_line.id] = mapping_line.field_id or mapping_line.external_field
        return res
    
    _columns = {
        'name_function': fields.function(_name_get_fnc, type="char", string='Full Name'),
    }

external_mapping_line()


class external_mapping(osv.osv):
    _name = 'external.mapping'
    _description = 'External Mapping'
    _rec_name = 'model'
    
    def _related_model_ids(self, cr, uid, model):
        field_ids = self.pool.get("ir.model.fields").search(cr, uid, [('model_id', '=', model.id), ('ttype', '=', 'many2one')])
        model_names = Set([model.model])
        for field in self.pool.get("ir.model.fields").browse(cr, uid, field_ids):
            model_names.add(field.relation)
        model_ids = self.pool.get("ir.model").search(cr, uid, [('model', 'in', [name for name in model_names])])
        return model_ids
    
    def _get_related_model_ids(self, cr, uid, ids, name, arg, context=None):
        "Used to retrieve model field one can map without ambiguity. Fields can come from Inherited objects or other many2one relations"
        res = {}
        for mapping in self.browse(cr, uid, ids, context): #FIXME: could be fully recursive instead of only 1 level
            res[mapping.id] = self._related_model_ids(cr, uid, mapping.model_id)
        return res
    
    def model_id_change(self, cr, uid, ids, model_id=None):
        if model_id:
            model = self.pool.get('ir.model').browse(cr, uid, model_id)
            return {'value': {'related_model_ids': self._related_model_ids(cr, uid, model)}}
        else:
            return {}

    def create_external_link(self, cr, uid, model, model_name):
        vals = {'domain': "[('res_id', '=', 'active_id'), ('model', '=', '%s')]" %(model,), 'name': 'External ' + model_name, 'res_model': 'ir.model.data', 'src_model': model, 'view_type': 'form'}
        xml_id = "ext_" + model.replace(".", "_")
        ir_model_data_id = self.pool.get('ir.model.data')._update(cr, uid, 'ir.actions.act_window', "base_external_referentials", vals, xml_id, False, 'update')
        value = 'ir.actions.act_window,'+str(ir_model_data_id)
        return self.pool.get('ir.model.data').ir_set(cr, uid, 'action', 'client_action_relate', xml_id, [model], value, replace=True, isobject=True, xml_id=xml_id)

    def create(self, cr, uid, vals, context=None):
        res = super(external_mapping, self).create(cr, uid, vals, context)
        data = self.pool.get('ir.model').read(cr, uid, [vals['model_id']], ['model', 'name'], context)[0]
        model = data['model']
        model_name = data['name']
        self.create_external_link(cr, uid, model, model_name)
        return res
    
    _columns = {
        'referential_id': fields.many2one('external.referential', 'External Referential', required=True, ondelete='cascade'),
        'model_id': fields.many2one('ir.model', 'OpenERP Model', required=True, ondelete='cascade'),
        'model':fields.related('model_id', 'model', type='char', string='Model Name'),
        'related_model_ids': fields.function(_get_related_model_ids, type="one2many", relation="ir.model", string='Related Inherited Models', help="potentially inherited through '_inherits' model, used for mapping field selection"),
        'external_list_method': fields.char('List Method', size=64),
        'external_get_method': fields.char('Get Method', size=64),
        'external_update_method': fields.char('Update Method', size=64),
        'external_create_method': fields.char('Create Method', size=64),
        'external_delete_method': fields.char('Delete Method', size=64),
        'mapping_ids': fields.one2many('external.mapping.line', 'mapping_id', 'Mappings Lines'),
        'external_key_name':fields.char('External field used as key', size=64),
        'external_resource_name':fields.char('External Resource Name', size=64),
    }

    # Method to set mapping with all object files
    def add_all_fields(self, cr, uid, ids, context={}):
        mapping_line_obj = self.pool.get('external.mapping.line')
        mapping = self.browse(cr, uid, ids)[0]
        for field in mapping.model_id.field_id:
            vals = {'mapping_id': mapping.id,
                    'field_id': field.id,
                    'type' : 'in_out',
                    'active' : True,
                    }
            mapping_line_obj.create(cr, uid, vals)
        return True

    # Method to export the mapping file
    def create_mapping_file(self, cr, uid, ids, context={}):
        csv_file = "\"id\",\"version_id:id\",\"model_id:id\",\"external_field\",\"field_id:id\",\"type\",\"evaluation_type\",\"external_type\",\"child_mapping_id:id\",\"in_function\",\"out_function\"\n"
        mapping = self.browse(cr, uid, ids)[0]
        for line in mapping.mapping_ids:
            if line.external_field!=False and line.selected==True:
                current_model = mapping.model_id.get_external_id(context=context)[mapping.model_id.id]
                current_field = line.field_id.get_external_id(context=context)[line.field_id.id]
                print mapping.referential_id.version_id.get_external_id(context=context)[mapping.referential_id.version_id.id]

                csv_file += "\""+mapping.referential_id.version_id.get_external_id(context=context)[mapping.referential_id.version_id.id]+"_"+mapping.model_id.name+"_"+line.field_id.name+"_"+line.external_field+"\","
                csv_file += "\""+mapping.referential_id.version_id.get_external_id(context=context)[mapping.referential_id.version_id.id]+"\","
                csv_file += "\""+current_model+"\","
                csv_file += "\""+line.external_field+"\","
                csv_file += "\""+current_field+"\","
                csv_file += "\""+line.type+"\","
                if line.evaluation_type!=False:
                    csv_file += "\""+line.evaluation_type+"\","
                else:
                    csv_file += "\"\","
                if line.external_type!=False:
                    csv_file += "\""+line.external_type+"\","
                else:
                    csv_file += "\"\","
                if line.child_mapping_id.id!=False:
                    csv_file += "\""+line.child_mapping_id.get_external_id(context=context)[line.child_mapping_id.id]+"\","
                else:
                    csv_file += "\"\","
                if line.in_function!=False:
                    csv_file += "\""+line.in_function+"\","
                else:
                    csv_file += "\"\","
                if line.out_function!=False:
                    csv_file += "\""+line.out_function+"\"\n"
                else:
                    csv_file += "\"\"\n"
        raise osv.except_osv(_('Mapping lines'), _(csv_file))
        return True
                
external_mapping()


class external_mapping_line(osv.osv):
    _inherit = 'external.mapping.line'
    
    _columns = {
        'field_id': fields.many2one('ir.model.fields', 'OpenERP Field', ondelete='cascade'),
        'field_real_name': fields.related('field_id', 'name', type='char', relation='ir.model.field', string='Field name',readonly=True),
        
        'external_field': fields.char('External Field', size=32),
        'mapping_id': fields.many2one('external.mapping', 'External Mapping', ondelete='cascade'),
        'related_model_id': fields.related('mapping_id', 'model_id', type='many2one', relation='ir.model', string='Related Model'),
        'type': fields.selection([('in_out', 'External <-> OpenERP'), ('in', 'External -> OpenERP'), ('out', 'External <- OpenERP')], 'Type'),
        'external_type': fields.selection([('o2m', 'one2many'), ('unicode', 'String'), ('bool', 'Boolean'), ('int', 'Integer'), ('float', 'Float'), ('list', 'List'), ('dict', 'Dictionnary')], 'External Type', required=True),
        'evaluation_type': fields.selection([('function', 'Function'), ('sub-mapping','Sub Mapping Line'), ('direct', 'Direct Mapping')], 'Evalution Type', required=True),
        'in_function': fields.text('Import in OpenERP Mapping Python Function'),
        'out_function': fields.text('Export from OpenERP Mapping Python Function'),
        'sequence': fields.integer('Sequence'),
        'active': fields.boolean('Active', help="if not checked : not printed in report"),
        'selected': fields.boolean('Selected', help="to select for mapping"),
        'child_mapping_id': fields.many2one('external.mapping', 'Child Mapping',
            help=('This give you the possibility to import data with a structure of Parent/child'
                'For example when you import a sale order, the sale order is the parent of the sale order line'
                'In this case you have to select the child mapping in order to convert the data'
                )
            ),
    }
    
    _defaults = {
         'type' : lambda * a: 'in_out',
         'external_type': lambda *a: 'unicode',
         'evaluation_type': lambda *a: 'direct',
    }
    
    def _check_mapping_line_name(self, cr, uid, ids):
        for mapping_line in self.browse(cr, uid, ids):
            if (not mapping_line.field_id) and (not mapping_line.external_field):
                return False
        return True
    
    _constraints = [
        (_check_mapping_line_name, "Error ! Invalid Mapping Line Name: Field and External Field cannot be both null", ['parent_id'])
    ]
    
    _order = 'type,external_type'
    #TODO add constraint: not both field_id and external_field null
external_mapping_line()

class ir_model_data(osv.osv):
    _inherit = "ir.model.data"
    
    def init(self, cr):
      #FIXME: migration workaround: we changed the ir_model_data usage to make standard CSV import work again
      cr.execute("select name from external_referential;")
      referentials = cr.fetchall()
      for tuple in referentials:
          name = "extref." + tuple[0]
          cr.execute("update ir_model_data set name = replace(name, '_mag_order', '/mag_order') where module = %s;", (name,))
          cr.execute("update ir_model_data set name = regexp_replace(name, '_([1-9])', E'/\\\\1') where module = %s;", (name,))
          cr.execute("update ir_model_data set name = replace(name, '.', '_') where module = %s;", (name,))
          cr.execute("update ir_model_data set module = replace(module, '.','/') where module = %s;", (name,))
      return True

    def _get_referential_id(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for model_data in self.browse(cr, uid, ids, context):
            s = model_data.module.split('/') #we assume a module name with a '/' means external referential
            if len(s) > 1:
                ref_ids = self.pool.get('external.referential').search(cr, uid, [['name', '=', s[1]]])
                if ref_ids:
                    res[model_data.id] = ref_ids[0]
                else:
                    res[model_data.id] = False
            else:
                res[model_data.id] = False
        return res

    _columns = {
        'referential_id': fields.function(_get_referential_id, type="many2one", relation='external.referential', string='Ext. Referential', store=True),
        #'referential_id':fields.many2one('external.referential', 'Ext. Referential'),
        #'create_date': fields.datetime('Created date', readonly=True), #TODO used?
        #'write_date': fields.datetime('Updated date', readonly=True), #TODO used?
    }
    
    _sql_constraints = [
        ('external_reference_uniq_per_object', 'unique(model, res_id, referential_id)', 'You cannot have on record with multiple external id for a sae referential'),
    ]

ir_model_data()
