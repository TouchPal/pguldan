import pguldan
client = pguldan.Client.instance("guldan or guldan proxy address", auto_refresh=True)
client.subscribe("org.proj.item", refresh)
print client.get_config("org.proj.item")
print client.get_config("org.proj.item2")

