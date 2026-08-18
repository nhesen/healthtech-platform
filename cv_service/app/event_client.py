import json, urllib.request
def send_event(backend_url:str,payload:dict)->dict:
    request=urllib.request.Request(f"{backend_url}/cv-events",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","X-Demo-User":"admin@demo.az"})
    with urllib.request.urlopen(request,timeout=5) as response:return json.loads(response.read())
