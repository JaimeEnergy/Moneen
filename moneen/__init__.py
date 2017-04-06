import os
import flask
import bokeh
import flask_cache

from flask import Flask, g, make_response
from flask_cache import Cache
import psycopg2
import pandas as pd
import numpy as np
import bokeh.plotting as plt

from bokeh.charts import TimeSeries
from bokeh.io import show, output_notebook
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.models import FixedTicker, HoverTool, Span
from bokeh.resources import CDN
from bokeh.embed import file_html
from urllib import parse
import sys # For Printing


app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
cache = Cache(app,config={'CACHE_TYPE': 'simple'})


parse.uses_netloc.append("postgres")
url = parse.urlparse(os.environ.get("DATABASE_URL", None))


#DATABASE = 'power.db'

def p(arg):
    print(arg, file=sys.stderr)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        try:
            db = g._database =  psycopg2.connect(
                                            database=url.path[1:],
                                            user=url.username,
                                            password=url.password,
                                            host=url.hostname,
                                            port=url.port
                                        )
        except:
            p("LOCAL DB")
            db =  psycopg2.connect("dbname=power user=postgres password=postgres")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/pr/<text>')
def add_power_reading(text):
    lines = text.split('!')
    conn = get_db()
    cursor = conn.cursor()
    # timestamp to timestamp
    #timestamp = datetime.datetime.strptime(timestamp,'%d-%m-%Y-%H:%M:%S')

    # reading to int
    #reading = int(reading)

    insert_query = None

    for line in lines:
        timestamp, power = line.split('-')

        # get power table

        sql = f"""
            INSERT INTO ActivePower(Timestamp, Power) VALUES(to_timestamp({timestamp}), {power})
            ON CONFLICT DO NOTHING
            """
        cursor.execute(sql)

    conn.commit()
    cursor.close()

    return make_response("Name accepted")

@cache.cached(timeout=30)
@app.route('/moneen')
def bokeh():

    for rule in app.url_map.iter_rules():
        p(rule)

    conn = get_db()
    cursor = conn.cursor()

    df = pd.read_sql(con=conn, sql='select * from activepower', index_col='timestamp')
    #df.index= df.index*1000000000
    #df.index = pd.to_datetime(source.index-1000000, utc=True)
    
    df = df.sort_index()
    diff = df.diff()
    
    rm = diff.rolling(window=180).mean()[180:][::60]
    source = rm.copy()

    source['hourly_min'] = rm.resample('H').min().reindex(df.index,method='ffill')
    source['hourly_max'] = rm.resample('H').max().reindex(df.index,method='ffill')
    source['date'] = rm.index.strftime('%a %d %b')
    source['time'] = rm.index.strftime('%H:%M')
    source['percent'] = rm['power'] * (100/(4.25)*36/100)

    #source = source.unstack()
    source = plt.ColumnDataSource(data=source)

    #p("READINGS")
    #p(len(source.data['power']))
    #p(source.data['date'])

    plot = plt.figure(
        width=800, height=600,
        x_axis_type="datetime",
        title = "Power (kWh)"
    )


    plot.line(
        x= 'timestamp', y='percent',
        source=source,
        alpha=1, color='#e24a33',
        line_width=2, legend = 'Power (MWh)'
    )

    hline = Span(location=100, dimension='width', line_color='green', line_width=3)

    plot.renderers.extend([hline])

    majorticks = [
        date.to_datetime64().astype('datetime64[ms]').view(np.int64)
        for date in df.index
        if date.hour == 0
        and date.minute == 00
    ]

    p(majorticks)

    minorticks = [
        date.to_datetime64().astype('datetime64[ms]').view(np.int64)
        for date in df.index
        if date.hour == 0
        and date.minute == 0
        and date not in majorticks
    ]

    plot.xgrid.ticker = FixedTicker(ticks=minorticks)

    plot.xaxis[0].ticker = FixedTicker(ticks=majorticks)

    # newline not respected in ticklabels !!!
    plot.xaxis.formatter = DatetimeTickFormatter(days=["%a\n%d %b"])

    plot.xgrid.band_fill_color = "grey"
    plot.xgrid.band_fill_alpha = 0.05

    plot.xaxis.axis_label = 'Date'
    plot.xaxis.axis_label_text_font_size = "12pt"
    plot.yaxis.axis_label = '% MWh'
    plot.yaxis.axis_label_text_font_size = "12pt"

    plot.legend.location = "bottom_right"

    #ts = TimeSeries(rm, x='index', y='values')

    hover = HoverTool()
    hover.tooltips  = """
        <div>
            <span style="font-size: 15px; font-weight: bold;">@date</span>
        </div>
        <table border="0" cellpadding="10">
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@time: </span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@power</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">hourly_min:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_min</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">hourly_max:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_max</span></td>
            </tr>
        </table>
    """

    plot.add_tools(hover)
    return file_html(plot, CDN, "some my plot")



        