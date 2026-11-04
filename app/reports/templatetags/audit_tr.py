from django import template
from reports.forms import ACTIONS
register=template.Library()
@register.filter
def action_tr(value):return ACTIONS.get(value,value)
@register.filter
def object_tr(value):return {'File':'Dosya','Directory':'Klasör','Unknown':'Bilinmiyor','Success':'Başarılı','Failed':'Başarısız'}.get(value,value)
@register.filter
def size_gb(value):
    value=float(value or 0)
    return f'{value/1024**3:,.2f}'.replace(',','_').replace('.',',').replace('_','.')+' GB'
