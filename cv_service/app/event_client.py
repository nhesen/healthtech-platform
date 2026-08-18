import json, os, urllib.request
def send_event(backend_url:str,payload:dict)->dict:
    headers={"Content-Type":"application/json"};token=os.getenv("CV_SERVICE_TOKEN","")
    if token: headers["X-CV-Service-Key"]=token
    else: headers["X-Demo-User"]="admin@demo.az"
    request=urllib.request.Request(f"{backend_url}/cv-events",data=json.dumps(payload).encode(),headers=headers)
    with urllib.request.urlopen(request,timeout=5) as response:return json.loads(response.read())
