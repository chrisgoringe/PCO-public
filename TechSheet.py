import gradio as gr

import json, threading, queue
import requests
from requests.auth import HTTPBasicAuth

session = requests.session()

with open("auth.json") as f:
    params = json.load(f)

auth = HTTPBasicAuth(params['user'],params['pass'])

base = 'https://api.planningcenteronline.com/services/v2'

def get_service_types():
    r = session.get(f"{base}/service_types", auth=auth )
    types = {}
    for e in r.json()['data']:
        types[e['attributes']['name']] = e['id']
    return types

def get_plans(type):
    global type_id, plans
    type_id = service_types[type]
    r = session.get(f"{base}/service_types/{type_id}/plans", auth=auth, params={'order': '-sort_date', 'per_page': 5} )
    plans = {}
    for e in r.json()['data']:
        title = e['attributes']['title']
        title = f"{title} {e['attributes']['short_dates']}" if title is not None else e['attributes']['short_dates']
        plans[title] = e['id']
    return [gr.update(label="Now select the service", choices=list(plans), visible=True, value=list(plans)[0]), 
            gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True),]

def get_item_av(type_id, plan_id, item_id, item_note_id):
    r = session.get(f"{base}/service_types/{type_id}/plans/{plan_id}/items/{item_id}/item_notes/{item_note_id}", auth=auth)
    item_note = r.json()
    if (item_note['data']['attributes']['category_name'] == "Audio/Visual"):
        return item_note['data']['attributes']['content']
    return None

def get_url(item):
    r2 = session.get(item['links']['self']+"/attachments", auth=auth ).json()
    for att in r2['data']:
        try:
            return att['attributes']['remote_link'][:-1]+"0" 
        except:
            pass
    return None

style = 'font-size:14px; padding: 2px; background-color:white; color:black;'
musics:list[str] = [
    "TiS", "Reflection", "postlude", "Countdown", "TIS"
]

class Line:
    FORMATS:list[str] = [
        "<tr><td style='width:40%; "+style+"'>{0}</td><td style='"+style+"'>{2}</td><td style='width:40%; "+style+"'>{1}</td></tr>",
        "<p style='"+style+"'>{0}</p>",
        "<a style='"+style+"' href='{3}'>{0}</a><br/>",
    ]

    def __init__(self, form):
        self.title = ""
        self.description = ""
        self.av_note = ""
        self.url = ""
        self.form = 0
        for i, f in enumerate(formats):
            if form == f: self.form = i


    @property
    def include(self): 
        if self.form==0: 
            return True
        if self.form==1:
            return self.title and any( m in self.title for m in musics )
        if self.form==2:
            return self.url

    @property
    def formatted(self):
        return Line.FORMATS[self.form].format(self.title, self.description, self.av_note, self.url)
    
def process_line(item, form, i, q:queue.Queue):
    line = Line(form)
    line.url = get_url(item)
    for note in item['relationships']['item_notes']['data']:
        if (mav:=get_item_av(type_id, plan_id, item['id'], note['id'])): 
            line.av_note = mav
            break
    line.description = item['attributes'].get('description', None) or ""
    line.title = item['attributes'].get('title',None) or ""
    q.put((i,line.formatted if line.include else None))


def get_plan(plan, form): 
    global plan_id, type_id, plans, type_id
    plan_id = plans[plan]
    r = session.get(f"{base}/service_types/{type_id}/plans/{plan_id}/items", auth=auth, params={'include': 'item_notes'} )

    threads:list[threading.Thread] = []
    q = queue.SimpleQueue()

    threads = [ threading.Thread(target=process_line, args=[item, form, i, q]) for i,item in enumerate(r.json()['data']) ]

    n = len(threads)
    for t in threads: t.start()
    for t in threads: t.join()

    lines = ["" for _ in range(n)]
    while not q.empty():
        (i, txt) = q.get()
        lines[i] = txt

    text = "\n".join([l for l in lines if l])
    if form not in ['Just music', 'Just links']:
        text = "<table>" + text + '</table>'

    return [text, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),]

service_types = get_service_types()
plans = {}
type_id = None
plan_id = None
formats = ['Standard Printable', 'Just music', 'Just links']



with gr.Blocks() as server:
    type_dropdown = gr.Dropdown(list(service_types), label="Choose service type", value="Morning Service")
    choose_button = gr.Button("Load services")
    plan_dropdown = gr.Dropdown([''], label="First choose the service type...", interactive = True, visible = False)
    format_dropdown = gr.Dropdown(formats, label="Format", interactive = True, visible = False)
    fetch_button  = gr.Button("Load service details", visible = False)
    text_area = gr.HTML("details will appear here", elem_id="results", visible=False)
    choose_button.click(get_plans, inputs = type_dropdown, outputs = [plan_dropdown, fetch_button, text_area, type_dropdown, choose_button, format_dropdown])
    fetch_button.click(get_plan, inputs = [plan_dropdown, format_dropdown], outputs =  [text_area, plan_dropdown, fetch_button, format_dropdown])


server.launch(show_api=False, server_name="0.0.0.0")

