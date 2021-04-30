# -*- coding: utf-8 -*-
{
    'name': "Correccion de calculos de ventas",

    'summary': """
            -Calculos de Ventas Correccion.
       """,

    'description': """
        
    """,

    'author': "Jesus pozzo",
    'website': "http://www.mobilize.cl",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'ventas',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','sale','l10n_cl_fe'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        #'views/views.xml',

    ],
    # only loaded in demonstration mode
    'demo': [

    ],
}