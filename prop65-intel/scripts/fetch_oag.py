import subprocess, urllib.parse, datetime, time, os, calendar
base="https://oag.ca.gov/prop65/60-day-notice-results-export_details.csv"
os.makedirs("raw",exist_ok=True)
log=open("fetch.log","a")
y,m=2020,1
end=datetime.date(2026,11,24)
while datetime.date(y,m,1)<=end:
    last=calendar.monthrange(y,m)[1]
    for a,b in ((1,15),(16,last)):
        d0=datetime.date(y,m,a); d1=min(datetime.date(y,m,b),end)
        if d0>end: break
        fn=f"raw/{d0:%Y%m%d}_{d1:%Y%m%d}.csv"
        if os.path.exists(fn) and os.path.getsize(fn)>100: continue
        q={"combine":"","combine_1":"","field_prop65_defendant_value":"","date_filter[min][date]":d0.strftime("%m/%d/%Y"),"date_filter[max][date]":d1.strftime("%m/%d/%Y"),"field_prop65_product_value":"","sort_by":"field_prop65_id_value","items_per_page":"100","attach":"page_1"}
        url=base+"?"+urllib.parse.urlencode(q)
        for attempt in range(4):
            try:
                data=subprocess.run(["curl","-sS","-f","-m","120","-A","Mozilla/5.0 (Macintosh)",url],capture_output=True,check=True).stdout
                assert data.startswith(b'"AG Number"')
                open(fn,"wb").write(data)
                log.write(f"{fn} {len(data)}\n"); log.flush(); break
            except Exception as e:
                log.write(f"{fn} ERR {e}\n"); log.flush(); time.sleep(5*(attempt+1))
        time.sleep(1.0)
    m+=1
    if m==13: y,m=y+1,1
log.write("DONE\n"); log.close()
