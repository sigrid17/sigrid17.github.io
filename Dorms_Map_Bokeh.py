import pandas as pd
import numpy as np
import geopandas as gpd
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
import math

import gspread
from google.oauth2.service_account import Credentials

from bokeh.io import show, curdoc
from bokeh.models import (CDSView, ColorBar, ColumnDataSource,
                          CustomJS, CustomJSFilter, 
                          GeoJSONDataSource, HoverTool,
                          LinearColorMapper, Slider, DateRangeSlider,
                          DatetimeTickFormatter, BasicTicker,
                          Legend)
from bokeh.layouts import column, row, widgetbox, grid, layout
from bokeh.palettes import brewer, Turbo256, viridis, inferno, magma, plasma, YlOrRd
from bokeh.plotting import figure
from bokeh.io import output_file, show
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn, Div, HTMLTemplateFormatter


# # Load Shape file
path = '/Users/sigrid/Documents/Better_SG/Covid_Dorms/master-plan-2019-planning-area-boundary-no-sea/'
areas = gpd.read_file(path + 'master-plan-2019-planning-area-boundary-no-sea-geojson.geojson')

region = []
for i in range(0,55):
    soup = BeautifulSoup(areas['Description'][i], 'html.parser').get_text()
    start = soup.find("PLN_AREA_N ") + len("PLN_AREA_N ")
    end = soup.find("PLN_AREA_C")
    region.append(soup[start:end].strip())
    
areas['region'] = region
areas[['Name','region','geometry']].to_json()


# # Load data from Google Sheet
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_file('sigrid-1362-f23b3afad1e2.json', scopes=scope)
gc = gspread.authorize(credentials)

dorms = gc.open("dorms numbers")

# ## Dorms location
adresses = pd.DataFrame(dorms.worksheet("addresses").get_all_records())
adresses = adresses[adresses['Latitude']!='']

# ## Nb of cases

dfmarch = pd.DataFrame(dorms.worksheet("March").get_all_records())
dfapril = pd.DataFrame(dorms.worksheet("April").get_all_records())

dfall = pd.concat([dfmarch[['Date ','Dorms','New Cases','Cumulative total']],dfapril[['Date ','Dorms','New Cases','Cumulative total']]])
dfall.columns = ['date', 'dorms', 'newcases', 'cumtot']
dfall = dfall[dfall['date']!='']
dfall = dfall[dfall['newcases']!='']
dfall['cumtot'][dfall['cumtot']==''] = 0
dfall['date'] = [datetime.strptime(str(x), '%d/%m/%Y') for x in dfall['date']]
dfall.head()

data = pd.merge(dfall,adresses,how = 'left', left_on = 'dorms', right_on = 'Name')    
data['sizes'] = 10 + data['newcases'].astype(int) / 4

col = []
for val in data['newcases']: 
    if (val < 5):
        col0 = '#FFFFFF'
    elif (val < 10):
        col0 = '#fffcad'
    elif (val < 15):
        col0 = '#ffe577'
    elif (val < 20):
        col0 = '#ffcf86'
    elif (val < 25):
        col0 = '#fda63a'
    else:
        col0 = '#ff5a00'
    col.append(col0)
data['colors'] = col

data.columns = ['date', 'dorms', 'newcases', 'cumtot', 'Address', 'y',
       'x', 'Name', 'sizes', 'colors']


stdt = datetime.date(min(data['date']))
eddt = datetime.date(max(data['date']))
stp = (eddt-stdt).days

data['date2'] = [(datetime.date(x)-stdt).days for x in data['date']]

# # Overall data for chart

nbcases = dfall.groupby('date')['newcases'].sum().reset_index()
nbcases = nbcases[nbcases['newcases']!='']
nbcases['cumtot'] = nbcases['newcases'].cumsum()
nbcases = nbcases.reset_index()

# # Top 10 dorms per cumulative numbers

upcases = dfall[['dorms','newcases']][dfall['date'] == eddt]
upcases.columns = ['dorms','up']

topdorms = dfall.groupby('dorms')['newcases'].sum().reset_index()
topdorms = topdorms[topdorms['newcases']!='']
topdorms = topdorms.sort_values(by = 'newcases', ascending = False)
topdorms0 = topdorms[topdorms['newcases']==0]
topdorms = pd.merge(topdorms,upcases, how = 'left')
topdorms = topdorms.fillna(0)
topdorms = topdorms[topdorms['newcases']>0]

lastdata0 = pd.merge(topdorms0, adresses, how = 'left', left_on = 'dorms', right_on = 'Name')
lastdata0 = lastdata0[~pd.isnull(lastdata0['Latitude'])]
lastdata0.columns = ['dorms', 'newcases', 'Address', 'y', 'x', 'Name']


# change the map with cumsum of cases => recalculate table as numbers are wrong in the original file
# replace table with area chart 
lastdata = pd.merge(topdorms, adresses, how = 'left', left_on = 'dorms', right_on = 'Name')
lastdata['sizes'] = 10 + lastdata['newcases'].astype(int) / 4
col = []
for val in lastdata['newcases']: 
    if (val < 10):
        col0 = '#FFFFFF'
    elif (val < 20):
        col0 = '#fffcad'
    elif (val < 30):
        col0 = '#ffe577'
    elif (val < 40):
        col0 = '#ffcf86'
    elif (val < 50):
        col0 = '#fda63a'
    else:
        col0 = '#ff5a00'
    col.append(col0)
lastdata['colors'] = col

lastdata.columns = ['dorms', 'newcases', 'up', 'Address', 'y', 'x', 'Name','sizes', 'colors']

# # Transpose data for Area chart

tmp = data[data['dorms'].isin(lastdata['dorms'].to_list())]
tmp['newcases'] = tmp['newcases'].astype(int)

area_data = tmp[['date','dorms','newcases']].set_index(['date','dorms'], drop = True).unstack('dorms').reset_index()
area_data = area_data.fillna(0)
a1 = area_data['newcases'].cumsum()
area_data = pd.concat([area_data['date'],a1], axis = 1)
xcols = ['date'] + lastdata['dorms'].to_list()
area_data = area_data[xcols]

# # Create the Dashboard

output_file("Dashboard_" + eddt.strftime("%Y%m%d") +".html")

gwidth = 1000
geosource = GeoJSONDataSource(geojson = areas[['Name','region','geometry']].to_json())
# Create figure object.
p1 = figure(title = 'Covid-19 Cases in Dormitories on ' + eddt.strftime("%d %b %Y"), 
           plot_height = 600 ,
           plot_width = gwidth, 
           toolbar_location = 'below',
           tools = "pan, wheel_zoom, box_zoom, reset, tap")
p1.xgrid.grid_line_color = None
p1.ygrid.grid_line_color = None

# Create the map
reg = p1.patches('xs','ys', source = geosource,
                   fill_color = "whitesmoke",
                   line_color = 'gray', 
                   line_width = 0.25, 
                   fill_alpha = 1)

# Add dorms data
psource = ColumnDataSource(lastdata)
mx = int(math.ceil(max(lastdata['newcases']) / 100.0)) * 100
color_mapper = LinearColorMapper(palette= brewer['YlOrRd'][9][::-1], low=0, high=mx)
# brewer['YlOrRd'][9][::-1]
cases = p1.circle('x', 'y', source=psource, 
                  fill_color={'field': 'newcases', 'transform': color_mapper}, 
                  size="sizes", 
                  line_color="grey")
p1.add_tools(HoverTool(tooltips = [('Dorm','@dorms'),('Nb of cases','@{newcases} (+@{up})')], renderers = [cases]))
p1.xaxis.visible = False
p1.yaxis.visible = False
p1.title.text_font_size = '14pt'
p1.title.align = 'center'
# Side bar legend
colors = ["#FFFFFF", "#fffcad", "#ffe577", "#ffcf86", "#fda63a", "#ff5a00"]
mapper = LinearColorMapper(palette=colors, low=0, high=60)
color_bar = ColorBar(color_mapper=color_mapper, location=(0, 0))

p1.add_layout(color_bar, 'right')

# Add dorms with no cases
psource0 = ColumnDataSource(lastdata0)
cases0 = p1.circle('x', 'y', source=psource0, 
                  color='black', 
                  size=4)
p1.add_tools(HoverTool(tooltips = [('Dorm','@dorms'),('Nb of cases','0')], renderers = [cases0]))

p1.add_layout(color_bar, 'right')


# Line and Bar Chart
nbcases['tooltip'] = [x.strftime("%d %b") for x in nbcases['date']]
scases = ColumnDataSource(nbcases)

p2 = figure(plot_width=gwidth, plot_height=300, title = "Number of cases over time",x_axis_type="datetime")
# dot line for cumulative nb of cases
cuml = p2.line('date', 'cumtot', source=scases, 
        line_color="#00bcd4", 
        line_width=2)
cum = p2.circle('date', 'cumtot', source=scases, color="#00bcd4", size=4)
# bar chart for nb of new daily cases
new = p2.vbar(x = 'date', top = 'newcases', source=scases, 
              color="#b2ebf2", 
              width = 0.8*24*60*60*1000)
hover_tool = p2.add_tools(HoverTool(tooltips = [('Date','@tooltip'),
                                                ('New Cases','@newcases'),
                                                ('Total Cases','@cumtot')], 
                       formatters={'date': 'datetime'},
                       mode='vline',
                       renderers = [cum]))
# format x-axis 
p2.xaxis.ticker.desired_num_ticks = nbcases.shape[0]
p2.xaxis[0].formatter = DatetimeTickFormatter(days='%d %b')
p2.xaxis.major_label_orientation = 3.14/4

p2.title.text_font_size = '11pt'
p2.title.align = 'center'

legend = Legend(items=[
    ("Total Cases",   [cuml, cum]),
    ("New Cases", [new])
], location="top_left")
p2.add_layout(legend)

asource = ColumnDataSource(data=area_data)
area_data['tooltip'] = [x.strftime("%d %b") for x in area_data['date']]

acol = magma(area_data.shape[1]-2)
ll = area_data.columns[1:][:-1].to_list()[::-1]
p3 = figure(plot_width=gwidth, plot_height=520, 
            x_axis_type="datetime", 
            title = "Number of cases by dormitory")
va = p3.varea_stack(area_data.columns[1:][:-1].to_list()[::-1], x='date', source=asource, 
                    color = acol,
                   name = ll)
# format x-axis 
p3.xaxis.ticker.desired_num_ticks = area_data.shape[0] 
p3.xaxis[0].formatter = DatetimeTickFormatter(days='%d %b')
p3.xaxis.major_label_orientation = 3.14/4

p3.title.text_font_size = '11pt'
p3.title.align = 'center'

# split legend into 3 
itm = [(l1, [r]) for (l1, r) in zip(ll, va)]
ln = round(len(itm)/3) + 1 
itm1 = itm[0:ln]
itm2 = itm[ln:(2*ln)]
itm3 = itm[(2*ln):len(itm)]

legend1 = Legend(items=itm1, location = (0,-100))
legend2 = Legend(items=itm2, location = (300,-1))
legend3 = Legend(items=itm3, location = (550,100))
p3.add_layout(legend1, 'below')
p3.add_layout(legend2, 'below')
p3.add_layout(legend3, 'below')
p3.legend.label_text_font_size = '8pt'

p3.legend.margin = -40

# need to overlay line chart then add hover tool
la = p3.line('date',0,  source=asource, line_color="black", line_width = 0.1)
tltp = [('Date','@{tooltip}')] + [(x,'@{' + x + '}') for x in ll[::-1]]
p3.add_tools(HoverTool(tooltips = tltp, 
                       formatters={'date': 'datetime'},
                       mode='vline'))
# add table
fulldata = ColumnDataSource(area_data)
columns = [TableColumn(field="tooltip", title="Date")] + [TableColumn(field=x, title=x) for x in ll]
p4 = DataTable(source=fulldata, columns = columns,  width=gwidth-50, height=280)
div = Div(text='<h4 style="text-align:center;width:860px"> Details per Dormitory </h4>', 
          align = 'center', margin = (10,0,0,0),
          width=gwidth-50, height=50)

fig = show(column(p1,p2,p3,div,p4))




