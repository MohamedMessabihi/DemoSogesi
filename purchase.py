#-*- coding:utf-8 -*-
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.exceptions import ValidationError, Warning
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import logging
import time
from lxml import etree
import datetime

from openerp import netsvc
from openerp import tools


#############################################################
#modi messabihi pc

#modif messa lap 

#mnt c'est encore moi

########## nouvelle modif ########################

#ici laptop

calc returne x*y;


mqdlkjlskdjf


# ceci est une modif de pc dz


class purchase_order1(osv.osv):
	
	def addition (x, y):
		return x+y

	def wkf_confirm_order(self,cr,uid,ids,context=None):
		
		res = super(purchase_order,self).wkf_confirm_order(cr,uid,ids,context=context)
		order = self.browse(cr,uid,ids[0],context)
		if order.importation:
			self.transitaire_invoice_create(cr, uid, [order.id], context)
			self.douane_invoice_create(cr, uid, [order.id], context)
		return res

	def get_total(self,cr,uid,ids,fields,args,context=None):
		res = {}
		for line in self.browse(cr,uid,ids,context):
			tmp = 0
			for frais in line.frais_transit_entrepot:
				tmp += frais.montant
			res[line.id] = tmp + line.val_douanes_entrepot

		return res


	_inherit = 'purchase.order'
	_columns = {
		'importation' : fields.boolean("Importation"),
		'transitaire_id' : fields.many2one('res.partner', 'Transitaire'),
		'douane_id' : fields.many2one('res.partner', 'Douane'),
		'val_douanes_entrepot' : fields.float('Valeur en douanes'),
		
		'douane_invoice' : fields.many2one('account.invoice','Facture douane'),
		'transitaire_invoice' : fields.many2one('account.invoice','Facture transitaire'),
		'date_importation' : fields.datetime('Date D3'),
		'tva_douane' : fields.many2one('account.tax', 'Douane TVA', domain=[
			('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),

		'coef_multi' : fields.float('Coef multiplicateur',readonly=True),
		'cout_achat' : fields.one2many('cout.achat','order_id','Cout d\'achat'),
		'currency_imp_id': fields.many2one("res.currency","Devise"),

		'mise_en_consommation' : fields.boolean('Mise en entrepot'),
		'frais_transitaire_pdr' : fields.float('Frais transitaire'),
		'douane_pdr' : fields.float('Autre Douane'),
		'cout_achat1' : fields.function(get_total,string="Cout d'achat 1",type='float'),
		'company_currency' : fields.many2one('res.currency','Company Currency'),
		
	}

	_defaults = {
			'importation':False,
		}

	def onchange_pricelist(self, cr, uid, ids, pricelist_id, context=None):
		res = super(purchase_order,self).onchange_pricelist(cr, uid, ids, pricelist_id, context)
		user = self.pool.get('res.users').browse(cr,uid,uid,context)
		pricelist = self.pool.get('product.pricelist').browse(cr,uid,pricelist_id,context)
		if user.company_id.currency_id:
			if pricelist.currency_id != user.company_id.currency_id:
				if pricelist_id:
					res['value']['importation'] = True
					res['value']['currency_imp_id'] = pricelist.currency_id
			else:
				if pricelist_id:
					res['value']['importation'] = False
					res['value']['currency_imp_id'] = False
		return res

	def actualiser2(self,cr,uid,ids,context=None):
		douane_valeur_total = 0.00
		valeur_en_douane = 0.00
		order = self.browse(cr,uid,ids,context)
		invoice_obj = self.pool.get('account.invoice')
		for order_line in order.frais_importation:
			douane_valeur_total += order_line.douane_valeur
			valeur_en_douane += order_line.frais_fournisseur_company_currency

		for order_line in order.frais_importation:
			transitaire_pourcentage = 0
			transitaire_valeur = 0
			autre_douane_valeur = 0
			total = 0
			coef_multiplicateur = 0
			if (douane_valeur_total !=0):
				transitaire_pourcentage = order_line.douane_valeur / douane_valeur_total * 100
				transitaire_valeur = order_line.order_id.transitaire_invoice.amount_untaxed * transitaire_pourcentage / 100
				autre_douane_valeur = order_line.order_id.douane_pdr * transitaire_pourcentage / 100
				total = order_line.frais_fournisseur_company_currency + order_line.douane_valeur + transitaire_valeur + autre_douane_valeur
				coef_multiplicateur = total / order_line.frais_fournisseur
			self.pool.get('frais.importation').write(cr,uid,order_line.id,{
				'transitaire_pourcentage': transitaire_pourcentage,
				'transitaire_valeur': transitaire_valeur,
				'autre_douane_valeur': autre_douane_valeur,
				'total': total,
				'coef_multiplicateur': coef_multiplicateur,
				},context)

		ligne_ids = self.pool.get('account.invoice.line').search(cr,uid,[('invoice_id','=',order.douane_invoice.id)])
		if ligne_ids:
			self.pool.get('account.invoice.line').unlink(cr,uid,ligne_ids,context)
		ir_model_obj = self.pool.get('ir.model.data')
		account_account = self.pool.get('account.account')
		account_account_template = self.pool.get('account.account.template')

		accounts_template_380 = ir_model_obj.get_object_reference(cr, uid,'l10n_dz', 'account38000')
		accounts_template_380_id = accounts_template_380 and accounts_template_380[1] or False
		account_template_380 = account_account_template.browse(cr,uid,accounts_template_380_id)
		account_380 = account_account.search(cr,uid,[('code','=', account_template_380.code)], limit=1)

		line_ids = []
		tva_tot = (douane_valeur_total + valeur_en_douane) * (order.tva_douane.amount)
		dd_id = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "Droit douane",'account_id': account_380[0],'price_unit': douane_valeur_total})
		tva_id = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "TVA",'account_id': order.tva_douane.account_collected_id.id,'price_unit': tva_tot})
		autre_id = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "Autre Douane",'account_id': account_380[0],'price_unit': order.douane_pdr})
		line_ids.append(dd_id)
		line_ids.append(tva_id)
		line_ids.append(autre_id)

		date = datetime.datetime.strptime(order.date_importation,'%Y-%m-%d %H:%M:%S').date()
		for invoice in order.invoice_ids:
			invoice_obj.write(cr,uid,invoice.id,{
				'date_invoice': date,
				})
		invoice_obj.write(cr,uid,order.douane_invoice.id,{
			'invoice_line': [(6, 0, line_ids)],
			})
		

		return {}

	def transitaire_invoice_create(self,cr,uid,ids,context=None):
		ir_model_obj = self.pool.get('ir.model.data')
		account_account = self.pool.get('account.account')
		account_account_template = self.pool.get('account.account.template')
		account_tax = self.pool.get('account.tax')
		account_tax_template = self.pool.get('account.tax.template')

		accounts_template_380 = ir_model_obj.get_object_reference(cr, uid,'l10n_dz', 'account38000')
		accounts_template_380_id = accounts_template_380 and accounts_template_380[1] or False
		account_template_380 = account_account_template.browse(cr,uid,accounts_template_380_id)
		account_380 = account_account.search(cr,uid,[('code','=', account_template_380.code)], limit=1)

		taxes_template_7 = ir_model_obj.get_object_reference(cr, uid,'l10n_dz', 'tva_acq_normale_temp')
		taxe_template_7_id = taxes_template_7 and taxes_template_7[1] or False
		taxe_template_7 = account_tax_template.browse(cr,uid,taxe_template_7_id)
		taxe_7 = account_tax.search(cr,uid,[('name','=', taxe_template_7.name)], limit=1)

		taxes_template_17 = ir_model_obj.get_object_reference(cr, uid,'l10n_dz', 'tva_acq_normale')
		taxe_template_17_id = taxes_template_17 and taxes_template_17[1] or False
		taxe_template_17 = account_tax_template.browse(cr,uid,taxe_template_17_id)
		taxe_17 = account_tax.search(cr,uid,[('name','=', taxe_template_17.name)], limit=1)

		line_ids = []
		sans_tva = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "Lignes sans TVA",'account_id': account_380[0],'invoice_line_tax_id': False})
		tva_7 = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "Lignes avec TVA 7%",'account_id': account_380[0],'invoice_line_tax_id': [(6, 0, taxe_7)]})
		tva_17 = self.pool['account.invoice.line'].create(cr,uid,{
			'name' : "Ligne avec TVA 17%",'account_id': account_380[0],'invoice_line_tax_id': [(6, 0, taxe_17)]})
		line_ids.append(sans_tva)
		line_ids.append(tva_7)
		line_ids.append(tva_17)

		order = self.browse(cr,uid,ids[0],context)
		inv_obj = self.pool.get('account.invoice')
		journal_ids = self.pool['account.journal'].search(
							cr, uid, [('type', '=', 'purchase'),
									  ('company_id', '=', order.company_id.id)],
							limit=1)
		if not journal_ids:
			raise osv.except_osv(
				_('Error!'),
				_('Veuillez configurer un journal d\'achat pour cette société: "%s" (id:%d).') % \
					(order.company_id.name, order.company_id.id))

		data = {
			'name': order.partner_ref or order.name,
			'reference': order.partner_ref or order.name,
			'account_id': order.transitaire_id.property_account_payable.id,
			'type': 'in_invoice',
			'partner_id': order.transitaire_id.id,
			'currency_id': order.company_id.currency_id.id,
			'journal_id': len(journal_ids) and journal_ids[0] or False,
			'invoice_line': [(6, 0, line_ids)],
			'origin': order.name,
			'fiscal_position': order.fiscal_position.id or False,
			'payment_term': order.payment_term_id.id or False,
			'company_id': order.company_id.id,
		}

		
		inv_id = inv_obj.create(cr, uid, data, context=context)
		inv_obj.button_compute(cr, uid, [inv_id], context=context, set_total=True)
		order.write({'invoice_ids': [(4, inv_id)]})
		order.write({'transitaire_invoice': inv_id})
		res = inv_id
		return res

	def douane_invoice_create(self,cr,uid,ids,context=None):
		line_ids = []
		order = self.browse(cr,uid,ids[0],context)
		inv_obj = self.pool.get('account.invoice')
		journal_ids = self.pool['account.journal'].search(
							cr, uid, [('type', '=', 'purchase'),
									  ('company_id', '=', order.company_id.id)],
							limit=1)
		if not journal_ids:
			raise osv.except_osv(
				_('Error!'),
				_('Veuillez configurer un journal d\'achat pour cette société: "%s" (id:%d).') % \
					(order.company_id.name, order.company_id.id))

		data = {
			'name': order.partner_ref or order.name,
			'reference': order.partner_ref or order.name,
			'account_id': order.douane_id.property_account_payable.id,
			'type': 'in_invoice',
			'partner_id': order.douane_id.id,
			'currency_id': order.company_id.currency_id.id,
			'journal_id': len(journal_ids) and journal_ids[0] or False,
			'invoice_line': [(6, 0, line_ids)],
			'origin': order.name,
			'fiscal_position': order.fiscal_position.id or False,
			'payment_term': order.payment_term_id.id or False,
			'company_id': order.company_id.id,
		}

		
		inv_id = inv_obj.create(cr, uid, data, context=context)
		inv_obj.button_compute(cr, uid, [inv_id], context=context, set_total=True)
		order.write({'invoice_ids': [(4, inv_id)]})
		order.write({'douane_invoice': inv_id})
		res = inv_id
		return res

	def onchange_importation(self,cr,uid,ids,importation,company_id,currency_imp_id,context=None):
		obj = self.pool.get('res.company').browse(cr,uid,company_id)
		res = {}


		if not importation:
			res = {'value' : {
				'currency_id' : obj.currency_id.id,
				'company_currency' : obj.currency_id.id,
				}}
		else:
			res = {'value' : {
				'currency_id' : currency_imp_id,
				'company_currency' : obj.currency_id.id,
			}}



		return res



	def action_fill_command_lines(self,cr,uid,ids,context=None):
		order = self.browse(cr,uid,ids[0],context)
		currency = order.currency_imp_id
		currency = currency.with_context(date=order.date_importation or datetime.datetime.now())

		frais_ids = self.pool.get('frais.importation').search(cr,uid,[('order_id','=',order.id)])
		if frais_ids:
			self.pool.get('frais.importation').unlink(cr,uid,frais_ids,context)

		douane_valeur_total = 0.00
		for order_line in self.browse(cr,uid,ids,context).order_line:
			frais_fournisseur_company_currency = currency.compute(order_line.price_subtotal, order.company_id.currency_id, round=False)
			douane_pourcentage = order_line.product_id.douane
			douane_valeur = frais_fournisseur_company_currency * douane_pourcentage / 100
			douane_valeur_total += douane_valeur

		for order_line in self.browse(cr,uid,ids,context).order_line:
			frais_fournisseur_company_currency = currency.compute(order_line.price_subtotal, order.company_id.currency_id, round=False)
			douane_pourcentage = order_line.product_id.douane
			douane_valeur = frais_fournisseur_company_currency * douane_pourcentage / 100
			if (douane_valeur_total ==0):
				transitaire_pourcentage = 0
			else:
				transitaire_pourcentage = douane_valeur / douane_valeur_total * 100
			transitaire_valeur = order.transitaire_invoice.amount_untaxed * transitaire_pourcentage / 100
			autre_douane_valeur = order.douane_pdr * transitaire_pourcentage / 100
			total = frais_fournisseur_company_currency + douane_valeur + transitaire_valeur + autre_douane_valeur
			coef_multiplicateur = total / order_line.price_subtotal
				
			self.pool.get('frais.importation').create(cr,uid,{
					'name':order_line.product_id.default_code,
					'line_id' : order_line.id,
					'product_id' : order_line.product_id.id,
					'p_unitaire':order_line.price_unit,
					'quantite':order_line.product_qty,
					'frais_fournisseur':order_line.price_subtotal,
					'frais_fournisseur_company_currency':frais_fournisseur_company_currency,
					'douane_pourcentage':douane_pourcentage,
					'douane_valeur':douane_valeur,
					'transitaire_pourcentage':transitaire_pourcentage,
					'transitaire_valeur':transitaire_valeur,
					'autre_douane_valeur':autre_douane_valeur,
					'total':total,
					'coef_multiplicateur':coef_multiplicateur,
					'order_id':order.id,
					},context)

		return True


	def calcul_cout(self,cr,uid,ids,context):
		order = self.browse(cr,uid,ids[0],context)
		frais1 = order.val_douanes_entrepot
		montant_devise = order.amount_untaxed
		cout_ids = self.pool.get('cout.achat').search(cr,uid,[('order_id','=',order.id)])
		if cout_ids:
			self.pool.get('cout.achat').unlink(cr,uid,cout_ids,context)

		for line in order.frais_importation:
			cout = line.p_unitaire * line.coef_multiplicateur
			self.pool.get('cout.achat').create(cr,uid,{
				'product_id' : line.product_id.id,
				'order_id' : line.order_id.id,
				'pu_devise' : line.p_unitaire,
				'qty' : line.quantite,
				'cout' : cout,
				'total' : cout * line.quantite,
				})
			s_move_id = self.pool.get('stock.move').search(cr,uid,[('purchase_line_id','=',line.line_id.id)])
			self.pool.get('stock.move').write(cr,uid,s_move_id,{
				'price_unit': cout,
				'prix_unitaire': line.p_unitaire,
				'currency_import': order.currency_id.id,
				})


		return True

purchase_order()


class cout_achat(osv.osv):
	_name="cout.achat"

	_columns = {
		'order_id' : fields.many2one('purchase.order'),
		'product_id' : fields.many2one('product.product','Produit'),
		'qty' : fields.integer('Qty'),
		'pu_devise' : fields.float('PU Devise', digits=(12,4)),
		'cout' : fields.float('CUA(DZD)', digits=(12,4)),
		'total' : fields.float('Total(DZD)', digits=(12,4)),
	}

cout_achat()


class purchase_order_line(osv.osv):
	_inherit="purchase.order.line"

	def get_importation(self,cr,uid,ids,args,fields,context=None):
		res = {}

		for line in self.browse(cr,uid,ids,context):
			res[line.id] = line.order_id.importation

		return res

	_columns ={
				'currency_imp_id': fields.related('order_id',"currency_imp_id",type="many2one",relation="res.currency",string="Devise"),
				'importation': fields.function(get_importation,string="Importation",type="boolean"),#related('order_id',"importation",type="boolean",string="Importation",readonly=True),
				}

	"""def action_confirm(self,cr,uid,ids,context=None):
		res = super(purchase_order_line,self).action_confirm(cr,uid,ids,context)
		for line in self.browse(cr,uid,ids,context):
			if (line.order_id.importation):
				pass
			else:
				self.pool.get('product.product').write(cr,uid,line.product_id.id,{'purchase_cost':line.price_unit},context)
		return res	"""


purchase_order_line()










