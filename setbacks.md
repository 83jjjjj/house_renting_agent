
我自己编写的简单house_renting_agent运行时踩坑：
1. python使用的windows宿主机的pycharm跑的，mysql是wsl2虚拟机跑的，程序网络访问不到mysql -> 最佳实践是wsl里采用docker部署mysql，外部可以localhost访问，原因不解
2. toolnode理解不到位，工具用@tool封装成runnable，ToolNode封装工具调用为节点，经过该节点后可能仍需走llm结合工具完成输出

运行recommend子图单元测试时踩坑：
1. 导入包的路径需要从项目根目录出发
2. Field里的default是给默认值而非类型，也就是None而非float|None
3. 默认值，llm可能不给None，而是给""，需要将""也视为None去更新
4. dict的get方法，只有当key不存在才取默认，即使是value为None也取出来None，所以model dump应当除去None

运行主图全流程时踩坑：
1. 在中断获取到用户个人信息后，llm给出no message content的ai message，因为上一条消息是推荐房源的ai message，llm不予回答 -> 补充一条human message指令即可
2. store put时直接往list里append了reservation对象，导致获取出来不是dict -> 只需先model dump再append即可
3. 存入memory的数据比如user_id应当强转为str，否则会报TypeError: '<' not supported between instances of 'int' and 'str'
4. 不需要调工具时不要绑定工具，避免收集工具参数的倾向
5. 伪造的消息也应存入messages，避免信息不全，比如中断收集到的

痛点：
1. 路由后流程中不能应对意外输出
2. 数据库的列值需要精确匹配，对不上就找不到
3. 

改造点：
1. 思考过程基于custom自定义
2. 语义查询数据库，避免精确匹配不到导致数据库不可用
3. 上下文管理，做摘要
