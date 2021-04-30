# -*- coding: utf-8 -*-


from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare


from odoo.addons import decimal_precision as dp

from werkzeug.urls import url_encode
import logging


class InheritOrder(models.Model):
    _inherit = "sale.order"
    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            logging.info("TOTALES DEL DOCUMENTO PRINCIPAL")
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            logging.info("padre tax : {}".format(amount_tax))
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })


class InheritSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'



    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        logging.info("MEtodo de lineas")
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)       
            if len(taxes['taxes']) <= 1:#logica natural de odoo para las lineas del pedido
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
            else:#si es mas de 1 impuesto aplica una logica modificada para las lineas del pedido
                total_tax = 0
                for tax in taxes['taxes']:
                    tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                    if tax_search:
                        total_tax+= tax_search.amount
                        
                total_tax = total_tax / 100
                subtotal = round(taxes['total_included']/(1+total_tax))
                logging.info(subtotal)
                total_amount_tax = 0

                for tax in taxes['taxes']:
                    tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                    if tax_search:
                        tasa =  tax_search.amount/100
                        logging.info((tasa * subtotal))
                        total_amount_tax = total_amount_tax + (tasa * subtotal)#bien QA
            
                line.update({
                    'price_tax': round(total_amount_tax,2),#bien QA
                    'price_total': taxes['total_included'],#bien QA
                    'price_subtotal':subtotal ,#bien QA
                })
