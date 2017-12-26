# Guldan #
> guldan pure python client

## 安装 ##
## 使用源码
- `git clone https://github.com/TouchPal/pguldan.git`
- `cd pguldan`
- `python setup.py install`

## 用法 ##

### 单例模式 ###
#### 获取配置 ####
    import pguldan
    client = pguldan.Client.instance("guldan or guldan proxy address")
    print client.get_config("org.proj.item")

#### 订阅配置变更 ####
    import guldan
    def refresh(cache_id, result):
      print cache_id, result

    client = pguldan.Client.instance("guldan or guldan proxy address", auto_refresh=True)
    client.subscribe("org.proj.item", refresh)
    print client.get_config("org.proj.item")

