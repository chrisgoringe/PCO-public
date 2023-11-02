import gradio as gr

import json
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
            gr.update(visible=True), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), ]

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

def get_plan(plan, show_links):
    global plan_id, type_id, plans, type_id
    plan_id = plans[plan]
    r = session.get(f"{base}/service_types/{type_id}/plans/{plan_id}/items", auth=auth, params={'include': 'item_notes'} )
    text = f"<table style='{style}'></table>"
    inner_text = ""
    linked = []
    for item in r.json()['data']:
        url = get_url(item) if show_links else None
        av_note = ""
        for note in item['relationships']['item_notes']['data']:
            maybe_av_note = get_item_av(type_id, plan_id, item['id'], note['id'])
            if maybe_av_note is not None:
                av_note = maybe_av_note
                break
        description = item['attributes']['description'] if 'description' in item['attributes'] and item['attributes']['description'] is not None else ""
        title = item['attributes']['title']
        title = title + (f" - <a href=\"{url}\">link</a>" if url else "")
        if (url):
            linked.append(title)
        inner_text = f"{inner_text}<tr><td style='width:40%; {style}'>{title}</td><td style='{style}'>{av_note}</td><td style='width:40%; {style}'>{description}</td></tr>"
        text = f"<table style='font-size:12pt'>{inner_text}</table>"
    if (linked):
        text += f"<hr/>"
        text += "<div>" + "".join([f"<span style='{style}'>{text}</span><br/>" for text in linked]) + "</div>"
    return [text, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), ]

style = "font-size:14px; padding: 2px; background-color:white; color:black;"

service_types = get_service_types()
plans = {}
type_id = None
plan_id = None

with gr.Blocks() as server:
    type_dropdown = gr.Dropdown(list(service_types), label="Choose service type", value="Morning Service")
    choose_button = gr.Button("Load services")
    plan_dropdown = gr.Dropdown([''], label="First choose the service type...", interactive = True, visible = False)
    fetch_button  = gr.Button("Load service details (takes about 10s)", visible = False)
    show_links_check = gr.Checkbox(label="Show links", value=True, visible=False)
    text_area = gr.HTML("details will appear here", elem_id="results", visible=False)
    choose_button.click(get_plans, inputs = type_dropdown, outputs = [plan_dropdown, fetch_button, text_area, type_dropdown, choose_button, show_links_check])
    fetch_button.click(get_plan, inputs = [plan_dropdown, show_links_check], outputs =  [text_area, plan_dropdown, fetch_button, show_links_check])


server.launch(show_api=False, server_name="0.0.0.0")

