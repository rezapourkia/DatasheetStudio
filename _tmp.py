import pymupdf
path='example/MAX17201-MAX17215.pdf'
doc=pymupdf.open(path)
for pno in [24,25,26]:
    page=doc.load_page(pno-1)
    tabs=page.find_tables().tables
    print('---page',pno,'tabs',len(tabs))
    for ti,t in enumerate(tabs):
        data=t.extract()
        print('table',ti,'rows',len(data),'cols',len(data[0]) if data else 0)
        if not data:
            continue
        print('header', [str(c or '').encode('unicode_escape').decode() for c in data[0]])
        for r in data[1:12]:
            print([str(c or '').encode('unicode_escape').decode() for c in r])
