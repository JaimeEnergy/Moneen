import os
import flask
import bokeh
import flask_cache
import datetime

from flask import Flask, g, make_response, render_template, request, redirect, url_for, session
from flask_cache import Cache
import psycopg2
import pandas as pd
import numpy as np
import bokeh.plotting as plt

from bokeh.charts import TimeSeries
from bokeh.io import show, output_notebook
from bokeh.models.formatters import DatetimeTickFormatter
from bokeh.models import FixedTicker, HoverTool, Span, DatetimeTicker, OpenURL, TapTool
from bokeh.models.callbacks import CustomJS
from bokeh.resources import CDN
from bokeh.embed import file_html
from bokeh.embed import components
from urllib import parse
import sys # For Printing


def p(arg):
    print(arg, file=sys.stderr)


app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'a very secret key'
cache = Cache(app,config={'CACHE_TYPE': 'simple'})


parse.uses_netloc.append("postgres")
url = parse.urlparse(os.environ.get("DATABASE_URL", None))
p("DB URL")
p(url)
p("DB URL ABOVE")


#DATABASE = 'power.db'

def get_times():
    return [(i, "{0}:{1}".format(i//2,str(i%2*3) + '0')) for i in range(48)]



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

@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', None)
        password = request.form.get('password', None)

 
        if username and (username.lower()+'123' == password):
            session['username'] = username
            return redirect(url_for('bokeh', random=username))

        else:

            flash("Incorrect username or password")

    return render_template('login.html')

@app.route('/pr/<text>')
def add_power_reading(text):
    lines = text.split('!')
    
    #conn.autocommit = False
    
    # timestamp to timestamp
    #timestamp = datetime.datetime.strptime(timestamp,'%d-%m-%Y-%H:%M:%S')

    # reading to int
    #reading = int(reading)

    insert_query = None

    for line in lines:
        conn = get_db()
        cursor = conn.cursor()
        timestamp, power = line.split('-')

        # get power table

        sql = """
            INSERT INTO ActivePower(Timestamp, Power) VALUES(to_timestamp({timestamp}), {power})
            ON CONFLICT (Timestamp)  DO UPDATE
            SET Power = {power2};
            """.format(timestamp=timestamp, power=power, power2=power)
        p(sql)
        cursor.execute(sql)
        conn.commit()
    p("inserted")

        
    cursor.close()

    return make_response("Name accepted")


@app.route('/moneen')
@app.route('/moneen/<random>')
def bokeh(windfarm='moneen', random=None):


    if random:
        username = session.get('username', None)
        if not username or username.lower() != random.lower():
            return redirect(url_for('login'))

    

    """
        Create plot
        
    """

    TOOLS="pan,wheel_zoom,box_zoom,reset"
    TOOLS="wheel_zoom,box_zoom,reset"

    plot = plt.figure(
        width=800, height=200,
        x_axis_type="datetime",
        #title = "Power (kWh)",
        tools=TOOLS,
        responsive=True
    )


    """
        Get the data for the line chart
        - get df from db TODO: select time limit
        - sort index and take difference
        - get a rollwing window (each reading is 10 seconds so 180*10 = 30 min)
    """
    conn = get_db()
    df = pd.read_sql(con=conn, sql='select * from activepower', index_col='timestamp')
    p(df.shape)

    #df.to_csv('heroku_dump')
    df = df.sort_index()
    diff = df.diff()
    rm = diff.rolling(window=180).mean()[180:][10::60]


    """
        TODO: Do I need two separate data frames?


    """

    source = rm.copy()

    source['hourly_min'] = rm.resample('H').min().reindex(df.index,method='ffill')
    source['hourly_max'] = rm.resample('H').max().reindex(df.index,method='ffill')
    source['date'] = rm.index.strftime('%a %d %b')
    source['time'] = rm.index.strftime('%H:%M')
    source['percent'] = rm['power'] * (100/(4.25)*36/100)
    source.percent.apply(lambda x: min(x, 100))
    source.percent.apply(lambda x: max(x, 0))

    source = plt.ColumnDataSource(data=source)

    line = plot.line(
        x= 'timestamp', y='percent',
        source=source,
        alpha=1, color='#e24a33',
        line_width=2, legend = 'Power (MWh)'
    )

    hline = Span(location=100, dimension='width', line_color='green', line_width=3)

    import time
    now = time.mktime(datetime.datetime.now().timetuple()) * 1000
    vline = Span(location=now, dimension='height', line_color='red', line_width=1, line_dash=[4,4])

    plot.renderers.extend([hline, vline])

    # newline not respected in ticklabels !!!
    plot.xaxis.formatter = DatetimeTickFormatter(days=["%a\n%d %b"])

    plot.xgrid.band_fill_color = "grey"
    plot.xgrid.band_fill_alpha = 0.05

    #plot.xaxis.axis_label = 'Date'
    plot.xaxis.axis_label_text_font_size = "11pt"
    plot.yaxis.axis_label = '% Power'
    plot.yaxis.axis_label_text_font_size = "11pt"
    plot.yaxis.axis_label_text_font_style = "normal"
    plot.legend.location = "top_left"

    #ts = TimeSeries(rm, x='index', y='values')

    

    hover_line = HoverTool(renderers=[line])
    hover_line.tooltips  = """
        <div>
            <span style="font-size: 15px; font-weight: bold;">@time</span>
        </div>
        <table border="0" cellpadding="10">
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">1/2-hourly average: </span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@power MW</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">1/2-hourly_min:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_min MW</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">1/2-hourly_max:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_max MW</span></td>
            </tr>
        </table>
    """

    plot.add_tools(hover_line)
    

    col = None

    def add_outages_to_plot(plot, df):

        df['midpoint'] = df.startdate + (df.finishdate-df.startdate)/2
        df['midpoint'] = df.midpoint.apply(lambda x: np.datetime64(x).astype('datetime64[ms]').view(np.int64))
        df['duration'] = df.finishdate-df.startdate
        df['height'] = 100 - (df.availability)
        df['width'] = df.duration.apply(lambda x: x.total_seconds()*1000)
        df['start'] = df.startdate.dt.strftime("%A, %e %B %H:%M")
        df['finish'] = df.finishdate.dt.strftime("%A, %e %B %H:%M")
        df['y'] = 100 -(df['height']/2)

        rect = plot.rect(

                x = 'midpoint',
                y = 'y',
                height = 'height',
                width = 'width',
                color = 'purple',
                source=df
        )

        return rect

    def create_outages_datatable(df):

        from bokeh.models import ColumnDataSource
        from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
        source = ColumnDataSource(df)
        columns = [
            TableColumn(field="start", title="Start"),
            TableColumn(field="finish", title="Finish"),
            TableColumn(field="availability", title="% Available"),
            TableColumn(field="timestamp", title="Updated At"),
        ]

        table_height = len(df) * 24 + 30
        data_table = DataTable(source=source, columns=columns,row_headers=True, width=770, height=table_height,
          sizing_mode='scale_both' )

        return source, data_table

    plot_div, dt_div, bokeh_script = '','',''

    if random:
        random = random.lower()
        
        conn = get_db()
        cursor = conn.cursor()
        q = """select * from appointments where random = '{r}'""".format(r=random)


        df = pd.read_sql(con=conn, sql=q)

        if not df.empty:

            rect = add_outages_to_plot(plot,df)

            hover_rect = HoverTool(renderers=[rect])
            hover_rect.tooltips  = """
                <div>
                    <span style="font-size: 15px; font-weight: bold;">@date</span>
                </div><a href="http://www.bbc.co.uk">:
                <table border="0" cellpadding="10">
                    <tr>
                        <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">Start: </span></th>
                        <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@start MWh</span></td>
                    </tr>
                    <tr>
                        <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">End:</span></th>
                        <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@finish</span></td>
                    </tr>
                    <tr>
                        <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">% Available:</span></th>
                        <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@availability</span></td>
                    </tr>
                </table>
                </a>
            """

            plot.add_tools(hover_rect)

            
            
            url = "/appointment/{windfarm}/{random}/edit/@start".format(windfarm=windfarm,random=random)
            taptool = plot.select(type=TapTool)
            #taptool = rect.select(type=TapTool)

            alert_js = """
           
                console.log("PARENT: " + showDiv(source.data['jobnumber'][source.selected["1d"].indices]))

               
            """

            source, data_table   = create_outages_datatable(df)
            source.callback = CustomJS(
                args = dict(source=source),
                code = alert_js
            )

            from bokeh.layouts import column
            col = column(plot, data_table)
            bokeh_script, comps  = components({"plot":plot,"dt":data_table})
            plot_div, dt_div = comps['plot'], comps['dt']
            
            
    
    if not col:
        col = plot
        bokeh_script, plot_div  = components(plot)

    plot.xaxis[0].ticker = DatetimeTicker()

    
    return render_template("l2.html", windfarm=windfarm, random=random, 
        plot_div=plot_div, dt_div=dt_div, bs=bokeh_script)

@app.route("/appointment/<windfarm>/<random>/edit/", methods = ['GET', 'POST'])
@app.route("/appointment/<windfarm>/<random>/edit/<jid>", methods = ['GET', 'POST'])
def edit_appointment(windfarm, random, jid=None):

    
    if request.method == 'POST':
        p(request.form)
        #trader_email = turbine.windfarm.trader.email
        windfarm = request.form['turbine'].capitalize()
        jid = request.form['jid']
        start_date = request.form['start']
        start_time = request.form['start_time']

        finish_date = request.form['finish']
        finish_time = request.form['finish_time']
        random = request.form['random']
        p("RANDOM")
        p(random)

        st = start_date + " " + start_time
        ft = finish_date + " " + finish_time
        import datetime
        #p(datetime.datetime.strptime(st, "%d-%m-%Y %H-%M"))

        st = st.replace(":","-")
        ft = ft.replace(":","-")

        try:
            st = datetime.datetime.strptime(st, "%d-%m-%Y %H-%M")
        except:
            st = datetime.datetime.strptime(st, "%d-%m-%y %H-%M")

        try:
            ft = datetime.datetime.strptime(ft, "%d-%m-%Y %H-%M")
        except:
            ft = datetime.datetime.strptime(ft, "%d-%m-%y %H-%M")

        st = str(int(pd.to_datetime(st, utc=True).timestamp()))
        ft = str(int(pd.to_datetime(ft, utc=True).timestamp()))
        
        availability = request.form['curtailment']
        comments = request.form['comments']

        """

                IF JID UPDATE
                
                ELSE INSERT

        """

        p("JID JID")
        p(jid)
        p(type(jid))

        isjob = False

        try:
            int(jid)
            isjob=True
        except:
            pass 

        epoch_time = datetime.datetime.now()
        epoch_time = int(pd.to_datetime(epoch_time, utc=True).timestamp())

        if isjob:

            update_appointment_query = """
                UPDATE appointments 
                SET 
                startdate = to_timestamp({st}),
                finishdate = to_timestamp({ft}),
                availability = {availability}, 
                comments = '{comments}',
                timestamp = to_timestamp({epoch_time})

                WHERE jobnumber = {jid}
            """.format(**locals())

            p(update_appointment_query)

            query = update_appointment_query

        else:

            insert_appointment_query = """
            INSERT INTO appointments (windfarm, startdate, finishdate, availability, comments, random, timestamp)
            VALUES ('{windfarm}', to_timestamp({st}), to_timestamp({ft}), {availability}, '{comments}', '{random}', to_timestamp({epochtime}))
        """.format(**locals())

            query = insert_appointment_query

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(query)

        conn.commit()
        cursor.close()

        return """

            <html>
                <head>
                    <script>
                        window.onunload = function() {
                            alert("appointment added");
                        };
                    </script>
                </head>
            </html>

        """
    else:

    # Try to get the appointment

        start, finish, st, ft, avail = '','','','',''
        if jid:
            q = "select * from appointments where jobnumber={jid} AND random='{random}'".format(**locals())
            p(q)

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(q)
            row = cursor.fetchone()
            p(row)
            start = row[4].strftime("%d-%m-%y")
            finish  = row[5].strftime("%d-%m-%y")

            st = row[4].strftime("%H-%M")
            ft = row[5].strftime("%H-%M")

            avail = row[2]

        times= get_times()

        return render_template("editappointment.html", random=random, jid=jid, times=times,
                            start=start, finish=finish, st=st, ft=ft, avail=avail, windfarm=windfarm)

@app.route("/appointment/<windfarm>", methods = ['GET'])
@app.route("/appointment/<windfarm>/<random>", methods = ['GET'])
def appointment(windfarm, random=None):    
    
    """user = load_user()

    if not user or not user.role == 'Owner':

        return redirect(url_for('login'))
    

    turbines = user.get_user_turbines()

    p(turbines)"""

    p("DEF APPOINTMENT")

    times = get_times()
    
    return render_template('layout.html',  times = times, windfarm=windfarm, random=random)
        



@app.route("/process_appointment", methods = ['POST'])
def process_appointment():
    """    try:
            user = load_user()

        if not user:
            return redirect(url_for('login'))                 
        if request.method == 'POST':
        p(request.form)
        turbine = user.get_turbine(request.form['turbine'])
        assert turbine.windfarm.owner == user"""

    msg = "NO MESSAGE"

    if request.method == 'POST':
        p(request.form)
        windfarm = request.form['turbine'].capitalize()
        start_date = request.form['start']
        start_time = request.form['start_time']

        finish_date = request.form['finish']
        finish_time = request.form['finish_time']
        random = request.form['random']

        st = start_date + " " + start_time
        ft = finish_date + " " + finish_time
        import datetime
        p(datetime.datetime.strptime(st, "%d-%m-%Y %H:%M"))
        st = datetime.datetime.strptime(st, "%d-%m-%Y %H:%M")
        ft = datetime.datetime.strptime(ft, "%d-%m-%Y %H:%M")

        st = str(int(pd.to_datetime(st, utc=True).timestamp()))
        ft = str(int(pd.to_datetime(ft, utc=True).timestamp()))
        
        availability = request.form['curtailment']
        comments = request.form['comments']

        #turbine.add_appointment(curtailment, comments, start_date, finish_date)

        p("FINISHED ASSIGNMENT")

        msg = """Hi Energy Traders,

                A new appointment has been set at {windfarm} with the following details:
                Start: {st} 
                Finish: {ft}
                Level of curtailment: {availability}
                With the following comments:
                {comments}

                sending to {{trader_email}}

                Thank You.
        """.format(**locals())

        epoch_time = datetime.datetime.now()
        epoch_time = str(int(pd.to_datetime(epoch_time, utc=True).timestamp()))
        p("EPOCHT TIME")
        p(epoch_time)

        insert_appointment_query = """
            INSERT INTO appointments (windfarm, startdate, finishdate, availability, comments, random, timestamp)
            VALUES ('{windfarm}', to_timestamp({st}), to_timestamp({ft}), {availability}, '{comments}', '{random}', to_timestamp({epoch_time}))
        """.format(**locals())

        p(insert_appointment_query)


        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(insert_appointment_query)
        conn.commit()
        cursor.close()
            
    #return redirect(url_for('appointment', windfarm=windfarm.lower(), random=random))		
    #return msg
    return "Success!"

    """            p("MESSAGE:" + msg)

            import smtplib
            server = smtplib.SMTP('smtp.gmail.com', 587)

            server.starttls()
            server.login("mathbooking@gmail.com", "Tandem17!")
            
            server.sendmail("mathbooking@gmail.com", [trader_email, "Jaime.Martin@Student.GCD.ie"], msg)
            server.quit()
            p("SUCCESS")

        
    except Exception as e:
        pj("ERROR", e)"""


@app.route('/add_outage/<windfarm>/<random>')
def add_outage(windfarm, random=None):
    return render_template('addappointment.html', windfarm=windfarm, random=random, times=get_times())


@app.route('/logout')
def logout():
    session.pop('username')
    return redirect(url_for('login'))