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
class InheritAccountInvoice(models.Model):
    _inherit = "account.invoice"


    """
        Ahora bien VAMOS A CAMBIAR LA LOGICA DE COMO CALCULA LOS IMPUESTOS EN LA FACTURA.
        RECONSTRUIMOS EL METODO QUE SACA LOS TOTALES en las facturas.
    """
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        logging.info("CADA VEZ QuE MODIFICO LA LINEA DE PEDIDO.")
        for inv in self:
            
            subtotal = 0
            total_total_tax = 0
            for line in inv.invoice_line_ids:
                total_tax = 0
                if line.invoice_line_tax_ids:
                    for tax in line.invoice_line_tax_ids:
                        tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                        if tax_search:
                            total_tax+= tax_search.amount
                    total_tax = total_tax / 100
                    

                    subtotal = round(line.price_total/(1+total_tax))
                    total_amount_tax = 0
                    for tax in line.invoice_line_tax_ids:
                        tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                        if tax_search:
                            tasa =  tax_search.amount/100
                            total_amount_tax =round(total_amount_tax + (tasa * subtotal),2)#bien QA
                    logging.info(total_amount_tax)
                    total_total_tax = total_total_tax + total_amount_tax
                    #amount_tax += line.price_tax
            logging.info("TOTAL IMPUESTO : {}".format(total_total_tax))

        round_curr = self.currency_id.round
        AmountU = 0
        for line in self.invoice_line_ids:
            tx = sum([(i.amount/100) for i in line.invoice_line_tax_ids])
            AmountU += line.price_total / (1+tx)
 
        self.amount_untaxed = AmountU#sum(line.price_subtotal for line in self.invoice_line_ids)

        self.amount_tax = total_total_tax#sum(round_curr(line.amount_total) for line in self.tax_line_ids)
        
        self.amount_total = sum([line.price_total for line in self.invoice_line_ids])#self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        amount_tax_company_signed = self.amount_tax
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id
            amount_total_company_signed = currency_id._convert(self.amount_total, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
            amount_untaxed_signed = currency_id._convert(self.amount_untaxed, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
            amount_tax_company_signed = currency_id._convert(self.amount_tax, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today())
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
        self.amount_untaxed_invoice_signed = self.amount_untaxed * sign
        self.amount_tax_company_signed = amount_tax_company_signed * sign
        self.amount_tax_signed = self.amount_tax * sign




class InheritAccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"
    
    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        logging.info("LINEA DE FACTURA")
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)

        
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        if taxes:
            if len(taxes['taxes']) <= 1:#logica natural de odoo para las lineas de FACTURA
                logging.info("MENOS de uno")
                self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
                self.price_total = price_total_signed = taxes['total_included'] if taxes else self.price_subtotal
                if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                    currency = self.invoice_id.currency_id
                    date = self.invoice_id._get_currency_rate_date()
                    price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
                    price_total_signed = currency._convert(price_total_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
                sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
                self.price_subtotal_signed = price_subtotal_signed * sign
                self.price_total_signed = price_total_signed * sign
            else:
                total_tax = 0
                for tax in taxes['taxes']:
                    tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                    if tax_search:
                        total_tax+= tax_search.amount
                
                total_tax = total_tax / 100
                subtotal = round(taxes['total_included']/(1+total_tax))
   
                total_amount_tax = 0

                for tax in taxes['taxes']:
                    tax_search = self.env['account.tax'].search([('name','=',tax['name'])])
                    if tax_search:
                        tasa =  tax_search.amount/100
                        total_amount_tax = total_amount_tax + (tasa * subtotal)#bien QA
                price_subtotal_signed = subtotal
                price_total_signed =  taxes['total_included']
                sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
                logging.info(price_subtotal_signed)
                logging.info(sign)
                
                self.price_subtotal = subtotal
                self.price_total = taxes['total_included']
                if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                    currency = self.invoice_id.currency_id
                    date = self.invoice_id._get_currency_rate_date()
                    price_subtotal_signed = currency._convert(price_subtotal_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
                    price_total_signed = currency._convert(price_total_signed, self.invoice_id.company_id.currency_id, self.company_id or self.env.user.company_id, date or fields.Date.today())
                logging.info(price_subtotal_signed)
                a = price_subtotal_signed * sign
                self.price_subtotal_signed = a
                b = price_total_signed * sign
                self.price_total_signed = b






class CreateInvoice(models.TransientModel):
    _inherit="sale.advance.payment.inv"

    @api.multi
    def _create_invoice(self, order, so_line, amount):

        inv_obj = self.env['account.invoice']
        ir_property_obj = self.env['ir.property']

        account_id = False
        if self.product_id.id:
            account_id = order.fiscal_position_id.map_account(self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id).id
        if not account_id:
            inc_acc = ir_property_obj.get('property_account_income_categ_id', 'product.category')
            account_id = order.fiscal_position_id.map_account(inc_acc).id if inc_acc else False
        if not account_id:
            raise UserError(
                _('There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') %
                (self.product_id.name,))

        if self.amount <= 0.00:
            raise UserError(_('The value of the down payment amount must be positive.'))
        context = {'lang': order.partner_id.lang}
        if self.advance_payment_method == 'percentage':
            amount = order.amount_untaxed * self.amount / 100
            name = _("Down payment of %s%%") % (self.amount,)
        else:
            amount = self.amount
            name = _('Down Payment')
        del context
        taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
        if order.fiscal_position_id and taxes:
            tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_shipping_id).ids
        else:
            tax_ids = taxes.ids
        data = {
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_invoice',
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_invoice_id.id,
            'partner_shipping_id': order.partner_shipping_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'origin': order.name,
                'account_id': account_id,
                'price_unit': amount,
                'quantity': 1.0,
                'discount': 0.0,
                'uom_id': self.product_id.uom_id.id,
                'product_id': self.product_id.id,
                'sale_line_ids': [(6, 0, [so_line.id])],
                'invoice_line_tax_ids': [(6, 0, tax_ids)],
                'analytic_tag_ids': [(6, 0, so_line.analytic_tag_ids.ids)],
                'account_analytic_id': order.analytic_account_id.id or False,
            })],
            'currency_id': order.pricelist_id.currency_id.id,
            'payment_term_id': order.payment_term_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'team_id': order.team_id.id,
            'user_id': order.user_id.id,
            'company_id': order.company_id.id,
            'comment': order.note,
        }
        invoice = inv_obj.create(data)
        invoice.compute_taxes()
        invoice.message_post_with_view('mail.message_origin_link',
                    values={'self': invoice, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return invoice
    @api.multi
    def _get_amount_tax(self,inv):
        total19 = 0
        total20 = 0
        base19 = 0
        base20 = 0
        total305 = 0
        base305 = 0

        for l in inv.invoice_line_ids:
            for tax in l.invoice_line_tax_ids:
                if tax.amount == 19.0:
                    total19 += ( (l.price_unit * l.quantity) / (1+(sum([tax.amount for tax in l.invoice_line_tax_ids])/100))) * 0.19
                    base19 += ( (l.price_unit * l.quantity) / (1+ 0.19))

                if tax.amount == 20.50:
                    total20 += ( (l.price_unit * l.quantity) / (1+(sum([tax.amount for tax in l.invoice_line_tax_ids])/100))) * 0.205
                    base20 += ( (l.price_unit * l.quantity) / (1+ 0.205))
                
                if tax.amount == 31.50:
                    total305 += ( (l.price_unit * l.quantity) / (1+(sum([tax.amount for tax in l.invoice_line_tax_ids])/100))) * 0.315
                    base305 += ( (l.price_unit * l.quantity) / (1+ 0.315))


        taxes_grouped = inv.get_taxes_values()
        for tax in taxes_grouped.values():
          
            if tax['name'] == 'IVA 19% Venta':
                tax['amount'] = total19
                tax['base'] = base19
            elif tax['name'] == 'ILA Cervezas (20,5%)':
                tax['amount'] = total20
                tax['base'] = base20
            elif tax['name'] == 'ILA Licores (31,5%)':
            
                    tax['amount'] = total305
                    tax['base'] = base305


        tax_lines = inv.tax_line_ids.filtered('manual')
       

        for tax in taxes_grouped.values():
            tax_lines += tax_lines.new(tax)

        return tax_lines

    

    
    @api.multi
    def create_invoices(self):
        logging.info("CLASE PRIMARIA")
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method == 'delivered':
            logging.info("entra aqui hermanito 1 ")
            #aqui crea la factura del pedido
            inv = sale_orders.action_invoice_create()
            if inv:
                for invoice in inv:
                    fact = self.env['account.invoice'].browse(invoice)
                    for sale in sale_orders:
                        #actualizamos como calcula las tasa
                        fact.write({
                                    'amount_untaxed':sale.amount_untaxed,
                                    'amount_tax':sale.amount_tax,
                                    'amount_total':sale.amount_total,
                                    
                                    })
                    logging.info(fact.tax_line_ids)
                    fact.tax_line_ids = [(6, 0, [])]    
                    fact.tax_line_ids = self._get_amount_tax(fact)   
      
        elif self.advance_payment_method == 'all':
  
            sale_orders.action_invoice_create(final=True)
        else:
     
            # Create deposit product if necessary
            if not self.product_id:
                vals = self._prepare_deposit_product()
                self.product_id = self.env['product.product'].create(vals)
                self.env['ir.config_parameter'].sudo().set_param('sale.default_deposit_product_id', self.product_id.id)

            sale_line_obj = self.env['sale.order.line']
            for order in sale_orders:
                if self.advance_payment_method == 'percentage':
                    amount = order.amount_untaxed * self.amount / 100
                else:
                    amount = self.amount
                if self.product_id.invoice_policy != 'order':
                    raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                if self.product_id.type != 'service':
                    raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
                if order.fiscal_position_id and taxes:
                    tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_shipping_id).ids
                else:
                    tax_ids = taxes.ids
                context = {'lang': order.partner_id.lang}
                analytic_tag_ids = []
                for line in order.order_line:
                    analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
                so_line = sale_line_obj.create({
                    'name': _('Advance: %s') % (time.strftime('%m %Y'),),
                    'price_unit': amount,
                    'product_uom_qty': 0.0,
                    'order_id': order.id,
                    'discount': 0.0,
                    'product_uom': self.product_id.uom_id.id,
                    'product_id': self.product_id.id,
                    'analytic_tag_ids': analytic_tag_ids,
                    'tax_id': [(6, 0, tax_ids)],
                    'is_downpayment': True,
                })
                del context
                logging.info("ANTES DE CREAR la factura")
                self._create_invoice(order, so_line, amount)
        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()
        return {'type': 'ir.actions.act_window_close'}

