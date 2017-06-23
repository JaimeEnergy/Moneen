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
from bokeh.models import FixedTicker, HoverTool, Span, DatetimeTicker, OpenURL, TapTool, Legend
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
app.config["EXPLAIN_TEMPLATE_LOADING"] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = set(['txt','csv','xlsx'])

def allowed_file(filename):
    p("CHECK FILE ALLOWED" + '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app.secret_key = 'a very secret key'
#cache = Cache(app,config={'CACHE_TYPE': 'simple'})


parse.uses_netloc.append("postgres")
url = parse.urlparse(os.environ.get("DATABASE_URL", None))
p("DB URL")
p(url)
p("DB URL ABOVE")


#DATABASE = 'power.db'

def get_times():
    """
        Generate 48 30-minute time-period strings from 00:00 to 23:30
    """
    return [(i, "{0}:{1}".format(i//2,str(i%2*3) + '0')) for i in range(48)]

"""
    Set up the database
    Provide teardown for after request
"""

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        p("UPLOAD FILE POST" )
        p(str(request.files))
        # check if the post request has the file part
        if 'file' not in request.files:
            p('No file part')
            return 'gggg'
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            p('No selected file')
            return 'ffff'
            return redirect(request.url)
        if file and allowed_file(file.filename):
            #filename = secure_filename(file.filename)
            p(str(file.filename))
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            p(path)
            file.save(path)

            with open(path, 'r') as f:
                for line in f.readlines():
                    p(line)
            return 'uploaded: ' + str(file.filename)
    
    else:
        return(render_template('upload.html'))

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
            #db =  psycopg2.connect("dbname=power user=postgres password=postgres")

        db = g._database =  psycopg2.connect(
                                            database='d47m4vio2038al',
                                            user='dztqxaluqjeuhg',
                                            password='6bc78f4cde53d5eb1f189b3902c365f7646d8f6d58d1a944f84ce2b5777b7749',
                                            host='ec2-54-83-26-65.compute-1.amazonaws.com',
                                            port=5432
                                        )
        
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


"""
    Simple login checks if password is username + '123'
"""

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




@app.route('/moneen')
@app.route('/moneen/<user>')
@app.route('/moneen/<user>/outlook/<outlook>')
def bokehs(windfarm='moneen', user='', outlook=False):
    p("BOKEH outlook " + str(outlook))

    
    username = session.get('username', None)
    username = session.get('username', '')
    if not username or username.lower() != user.lower():
        #return redirect(url_for('login'))
        pass
    

    """
        Create plot
        
    """

    TOOLS="pan,wheel_zoom,box_zoom,reset"
    #TOOLS="wheel_zoom,box_zoom,reset"

    plot = plt.figure(
        width=800, height=200,
        x_axis_type="datetime",
        #title = "Power (kWh)",
        tools=TOOLS,
        responsive=True
    )

    plot = plt.figure(
        width=600, height=200,
        x_axis_type="datetime",
        #title = "Power (kWh)",
        tools=TOOLS,
        responsive=True,
        toolbar_location="above"
    )

    plot.xaxis[0].ticker = DatetimeTicker()
    """
        Get the data for the line chart
        - get df from db TODO: select time limit
        - sort index and take difference
        - get a rollwing window (each reading is 10 seconds so 180*10 = 30 min)
    """
    #p("GET CONN")
    conn = get_db()

    #p("GOT CONN")
    #df = pd.read_sql(con=conn, sql='select * from activepower', index_col='timestamp')
    power_df = pd.read_sql(con=conn, sql='select * from source order by timestamp')
    power_df['setpoint'] = 100

    

    

    #hline = Span(location=100, dimension='width', line_color='green', line_width=3)

    

    import time
    now = time.mktime(datetime.datetime.now().timetuple()) * 1000
    vline = Span(location=now, dimension='height', line_color='red', line_width=1, line_dash=[4,4])

    plot.renderers.extend([vline])

    # newline not respected in ticklabels !!!
    plot.xaxis.formatter = DatetimeTickFormatter(days=["%a %d %b"])

    plot.xgrid.band_fill_color = "grey"
    plot.xgrid.band_fill_alpha = 0.05

    #plot.xaxis.axis_label = 'Date'
    plot.xaxis.axis_label_text_font_size = "11pt"
    plot.yaxis.axis_label = '% Power'
    plot.yaxis.axis_label_text_font_size = "11pt"
    plot.yaxis.axis_label_text_font_style = "normal"
    plot.legend.location = "top_left"

    #ts = TimeSeries(rm, x='index', y='values')

    

    
    

    col = None

    

    def create_outages_datatable(df):

        #p("datatable columns\n"+df.columns)

        from bokeh.models import ColumnDataSource
        from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
        datefmt = DateFormatter(format="dd M yy h:mm")
        source = ColumnDataSource(df)
        columns = [
            TableColumn(field="startdate", title="Start",formatter=datefmt),
            TableColumn(field="finishdate", title="Finish",formatter=datefmt),
            TableColumn(field="availability", title="% Available"),
            TableColumn(field="timestamp", title="Updated At",formatter=datefmt),
        ]

        table_height = len(df) * 24 + 30
        data_table = DataTable(source=source, columns=columns,row_headers=True, width=600, height=table_height,
          sizing_mode='scale_both' )

        return source, data_table

    plot_div, dt_div, bokeh_script = '','',''

    
    user = user.lower()
    
    conn = get_db()
    cursor = conn.cursor()
    q = """select * from appointments where random = '{r}'""".format(r=user)


    df = pd.read_sql(con=conn, sql=q)

    if not df.empty:

        appointments = df

        for a,i in appointments.iterrows():
            start = i.startdate
            finish = i.finishdate
            setpoint = i.availability
            #print("start", start, finish)
            row_indexer = power_df[(power_df.timestamp > start) & (power_df.timestamp< finish)].index
            p(len(row_indexer))
            power_df.loc[row_indexer, 'setpoint'] = setpoint

        url = "/appointment/{windfarm}/{random}/edit/@start".format(windfarm=windfarm,random=user)
        #taptool = plot.select(type=TapTool)
        #taptool = rect.select(type=TapTool)

        alert_js = """
        
            console.log("PARENT: " + showDiv(source.data['jobnumber'][source.selected["1d"].indices]))

        """   

    # Add OLD Forecast Power by jittering averages of old values
    # get average values_to_take numbers and add randint
    i = 0
    values_to_take = 30

    import random

    max_index = max(power_df.index)

    while i < max_index:
        floor, ceiling = i, min(i+values_to_take-1, max_index)
        values = power_df.loc[floor:ceiling,'percent']
        avg = sum(values)/len(values)
        guess = avg + random.randint(-10,10)

        guess = 0 if guess < 0 else guess
        guess = 100 if guess > 100 else guess
        
        power_df.loc[floor:ceiling,'forecast'] = guess
    
        i+=values_to_take

    

    

    


    now = pd.Timestamp.now().tz_localize('GMT')

    readings = []

    if appointments.finishdate.max().tz_localize('GMT') > now:

        targeted_end = (appointments.finishdate.max() + datetime.timedelta(days=2)).round('24h').tz_localize('GMT')

    else:

        targeted_end = (power_df.timestamp.max() + datetime.timedelta(days=7)).round('24h').tz_convert('GMT')
        
    freq = pd.tslib.Timedelta('0 days 00:10:00')

    d = now

    # test comment for git
    while d < targeted_end:

        readings.append({
            'timestamp':d, 'setpoint':100
        })

        d += freq
        #p(d)

    forecast_av_df = pd.DataFrame(readings)

    for a,i in appointments.iterrows():
        #print(i)
        start = i.startdate
        finish = i.finishdate
        setpoint = i.availability
        #print("start", start, finish)
        row_indexer = forecast_av_df[(forecast_av_df.timestamp > start) & (forecast_av_df.timestamp < finish)].index
        #print(row_indexer, setpoint)
        forecast_av_df.loc[row_indexer, 'setpoint'] = setpoint

    

        
    previous_forecast = power_df.iloc[-1,]['forecast']

    i = 0

    values_to_take = 6

    import random

    while i < max(forecast_av_df.index):
        floor, ceiling = i, min(i+values_to_take-1, max(forecast_av_df.index))
        guess = previous_forecast + random.randint(-1,1)
        
        guess = 0 if guess < 0 else guess
        guess = 100 if guess > 100 else guess
        
        forecast_av_df.loc[floor:ceiling,'forecast'] = guess
    
        i+=values_to_take
        previous_forecast = guess
    

    
    
        
        

    power_source = plt.ColumnDataSource(data=power_df)

    step = plot.line(
            x= 'timestamp', y='setpoint',
            source=power_source,
            alpha=1, color='orange',
            line_width=1
        )

    old_power = plot.line(
        x= 'timestamp', y='forecast',
        source=power_source,
        alpha=1, color='pink',
        line_width=1
    )

    power = plot.line(
                x= 'timestamp', y='percent',
                source=power_source,
                alpha=1, color='green',
                line_width=1
            )

    forecast_source = plt.ColumnDataSource(data=forecast_av_df)
    
    forecast = plot.line (
        x ='timestamp', y='setpoint',
        source = forecast_source, color = 'orange', line_dash=[6,3]
    )

    forecast_power = plot.line (
        x ='timestamp', y='forecast',
        source = forecast_source, color = 'pink', 
         line_dash=[6,6]
    )


    legend = Legend(items=[
        ("Availability",   [step]),
        ("Old Forecast Power", [old_power]),
        ("Actual Power", [power]),
        ("Forecast Power", [forecast_power]),
        ("Forecast Availability", [forecast]),
        #("Now", [vline])
    ], location=(0, -40))

    plot.add_layout(legend, 'right')

    hover_line = HoverTool(renderers=[old_power])
    hover_line.tooltips  = """
        <div>
            <span style="font-size: 15px;">@date @time</span>
        </div>
        <table border="0" cellpadding="10">
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">30m avg: </span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@power MW</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">30m min:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_min MW</span></td>
            </tr>
            <tr>
                <th><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">30m max:</span></th>
                <td><span style="font-family:'Consolas', 'Lucida Console', monospace; font-size: 12px;">@hourly_max MW</span></td>
            </tr>
        </table>
    """

    plot.add_tools(hover_line)

    source, data_table   = create_outages_datatable(df)
    source.callback = CustomJS(
        args = dict(source=source),
        code = alert_js
    )

    #plot.legend.location = "top_left"
    plot.legend.click_policy= "hide"
    #plot.legend.background_fill_alpha = 0.01
    #plot.legend.location=(10, -30)
    

    from bokeh.layouts import column
    col = column(plot, data_table)

    leg = [rend for rend in plot.renderers if type(rend)==bokeh.models.annotations.Legend][0]



    bokeh_script, comps  = components({"plot":plot,"dt":data_table,"legend":leg})
    plot_div, dt_div, legend_div = comps['plot'], comps['dt'], comps['legend']
            
            
    
    if not col:
        col = plot
        bokeh_script, plot_div  = components(plot)

    

    if not outlook:
        template = "l2.html"
    else:
        template = "outlook.html"

    p("TEMPLATE BEING USED: " + template)
    return render_template(template, windfarm=windfarm, random=user, 
        plot_div=plot_div, dt_div=dt_div, bs=bokeh_script, legend_div = legend_div)

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