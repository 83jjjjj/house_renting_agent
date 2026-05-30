-- Local fixture data for SQL Exec evaluation.
-- Target database: house-renting-agent
-- If your local database name is different, change the USE statement below.
-- If your MySQL/MariaDB does not support utf8mb4_0900_ai_ci, replace it with utf8mb4_unicode_ci.

USE `house-renting-agent`;

CREATE TABLE IF NOT EXISTS `houses` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `user_id` bigint unsigned NOT NULL COMMENT '房东id',
  `title` varchar(50) NOT NULL COMMENT '标题',
  `rent_type` varchar(20) NOT NULL COMMENT '租房类型 -整租 -合租',
  `floor` int NOT NULL COMMENT '所在楼层',
  `all_floor` int NOT NULL COMMENT '总楼层',
  `house_type` varchar(20) NOT NULL COMMENT '户型',
  `rooms` varchar(20) NOT NULL COMMENT '居室',
  `position` varchar(20) NOT NULL COMMENT '朝向',
  `area` decimal(10,2) NOT NULL COMMENT '面积（平方米）',
  `price` decimal(10,2) NOT NULL COMMENT '价格（元）',
  `intro` varchar(2047) NOT NULL COMMENT '房屋介绍',
  `devices` varchar(255) NOT NULL COMMENT '设备',
  `head_image` varchar(110) NOT NULL COMMENT '头图',
  `images` varchar(2047) DEFAULT NULL COMMENT '房源图',
  `city_id` bigint NOT NULL COMMENT '城市id',
  `city_name` varchar(40) NOT NULL COMMENT '城市名',
  `region_id` bigint NOT NULL COMMENT '区域id',
  `region_name` varchar(40) NOT NULL COMMENT '区域名',
  `community_name` varchar(40) NOT NULL COMMENT '社区名',
  `detail_address` varchar(255) NOT NULL COMMENT '详细地址',
  `longitude` decimal(10,7) NOT NULL COMMENT '经度',
  `latitude` decimal(10,7) NOT NULL COMMENT '纬度',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_user_id` (`user_id`) USING BTREE,
  KEY `idx_rent_type` (`rent_type`) USING BTREE,
  KEY `idx_title` (`title`) USING BTREE,
  KEY `idx_community_name` (`community_name`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;

START TRANSACTION;

DELETE FROM `houses` WHERE `id` BETWEEN 99000000001 AND 99000000030;

INSERT INTO `houses` (
  `id`,
  `user_id`,
  `title`,
  `rent_type`,
  `floor`,
  `all_floor`,
  `house_type`,
  `rooms`,
  `position`,
  `area`,
  `price`,
  `intro`,
  `devices`,
  `head_image`,
  `images`,
  `city_id`,
  `city_name`,
  `region_id`,
  `region_name`,
  `community_name`,
  `detail_address`,
  `longitude`,
  `latitude`
) VALUES
(99000000001, 9001, '朝阳国贸朝南主卧独卫', 'worry_free_rental', 8, 18, '3室1厅1卫', 'one', 'south', 22.50, 4200.00, '朝阳国贸主卧，带独卫，近地铁，采光好。', 'toilet,aircondition,washer,cook,gas,broadband,heating', 'https://example.com/h/99000000001.jpg', 'https://example.com/h/99000000001_1.jpg', 110100, '北京', 110105, '朝阳', '国贸新城', '朝阳区国贸路1号', 116.4610000, 39.9090000),
(99000000002, 9002, '朝阳望京南向主卧带阳台', 'worry_free_rental', 12, 21, '3室1厅1卫', 'one', 'south', 24.00, 4800.00, '朝阳望京主卧，独卫可用，带阳台，近地铁14号线。', 'toilet,balcony,aircondition,washer,broadband,heating', 'https://example.com/h/99000000002.jpg', 'https://example.com/h/99000000002_1.jpg', 110100, '北京', 110105, '朝阳', '望京花园', '朝阳区望京街2号', 116.4810000, 39.9910000),
(99000000003, 9003, '朝阳三里屯整租一居室带厨房', 'whole_rent', 5, 12, '1室1厅1卫', 'one', 'south', 45.00, 6500.00, '朝阳三里屯一居室整租，不合租，带厨房，适合独居。', 'cook,gas,aircondition,icebox,washer', 'https://example.com/h/99000000003.jpg', 'https://example.com/h/99000000003_1.jpg', 110100, '北京', 110105, '朝阳', '三里屯公寓', '朝阳区三里屯路3号', 116.4540000, 39.9370000),
(99000000004, 9004, '朝阳团结湖整租一居室', 'whole_rent', 10, 20, '1室1厅1卫', 'one', 'east', 49.00, 8200.00, '朝阳团结湖一居室整租，不合租，安静，通勤方便。', 'cook,gas,aircondition,icebox,washer,heating', 'https://example.com/h/99000000004.jpg', 'https://example.com/h/99000000004_1.jpg', 110100, '北京', 110105, '朝阳', '团结湖小区', '朝阳区团结湖路4号', 116.4690000, 39.9330000),
(99000000005, 9005, '望京近地铁朝南两居室', 'whole_rent', 15, 26, '2室1厅1卫', 'two', 'south', 72.00, 9200.00, '望京两居室整租，近地铁，客厅明亮，适合小家庭。', 'cook,gas,aircondition,icebox,washer,broadband,heating', 'https://example.com/h/99000000005.jpg', 'https://example.com/h/99000000005_1.jpg', 110100, '北京', 110105, '望京', '望京西园', '朝阳区望京西园5号', 116.4815000, 39.9950000),
(99000000006, 9006, '望京SOHO旁两居室近地铁', 'whole_rent', 9, 22, '2室1厅1卫', 'two', 'south', 68.00, 9800.00, '望京附近两居室，近地铁和商场，带厨房。', 'cook,gas,aircondition,icebox,washer,broadband,heating', 'https://example.com/h/99000000006.jpg', 'https://example.com/h/99000000006_1.jpg', 110100, '北京', 110105, '望京', '望京SOHO公寓', '朝阳区望京SOHO 6号', 116.4825000, 39.9960000),
(99000000007, 9007, '浦东陆家嘴朝南整租一居', 'whole_rent', 18, 30, '1室1厅1卫', 'one', 'south', 50.00, 7200.00, '上海浦东陆家嘴一居室整租，朝南，近地铁。', 'cook,gas,aircondition,icebox,washer,broadband,heating', 'https://example.com/h/99000000007.jpg', 'https://example.com/h/99000000007_1.jpg', 310100, '上海', 310115, '浦东', '陆家嘴花园', '浦东新区陆家嘴路7号', 121.5020000, 31.2400000),
(99000000008, 9008, '浦东世纪公园朝南整租房', 'whole_rent', 7, 16, '1室1厅1卫', 'one', 'south', 46.00, 7800.00, '上海浦东整租房，朝南，周边生活便利。', 'cook,gas,aircondition,icebox,washer', 'https://example.com/h/99000000008.jpg', 'https://example.com/h/99000000008_1.jpg', 310100, '上海', 310115, '浦东', '世纪公园社区', '浦东新区锦绣路8号', 121.5540000, 31.2170000),
(99000000009, 9009, '朝阳双井带厨房舒适房源', 'whole_rent', 6, 18, '1室1厅1卫', 'one', 'south', 42.00, 4500.00, '预算友好，带厨房，适合一人居住。', 'cook,gas,aircondition,washer', 'https://example.com/h/99000000009.jpg', 'https://example.com/h/99000000009_1.jpg', 110100, '北京', 110105, '朝阳', '双井家园', '朝阳区双井路9号', 116.4680000, 39.8940000),
(99000000010, 9010, '朝阳酒仙桥带厨房房源', 'whole_rent', 11, 20, '1室1厅1卫', 'one', 'west', 47.00, 6900.00, '带厨房，家电齐全，靠近产业园。', 'cook,gas,aircondition,icebox,washer', 'https://example.com/h/99000000010.jpg', 'https://example.com/h/99000000010_1.jpg', 110100, '北京', 110105, '朝阳', '酒仙桥公寓', '朝阳区酒仙桥路10号', 116.4950000, 39.9720000),
(99000000011, 9011, '海淀中关村朝南主卧', 'worry_free_rental', 4, 12, '3室1厅1卫', 'one', 'south', 21.00, 3200.00, '海淀中关村主卧，朝南，近地铁。', 'aircondition,washer,broadband,heating', 'https://example.com/h/99000000011.jpg', 'https://example.com/h/99000000011_1.jpg', 110100, '北京', 110108, '海淀', '中关村小区', '海淀区中关村路11号', 116.3180000, 39.9840000),
(99000000012, 9012, '海淀五道口主卧独卫', 'worry_free_rental', 13, 24, '3室1厅1卫', 'one', 'south', 25.00, 5200.00, '海淀五道口主卧，带独卫，距离地铁近。', 'toilet,aircondition,washer,broadband,heating', 'https://example.com/h/99000000012.jpg', 'https://example.com/h/99000000012_1.jpg', 110100, '北京', 110108, '海淀', '五道口家园', '海淀区五道口路12号', 116.3370000, 39.9910000),
(99000000013, 9013, '海淀上地主卧', 'worry_free_rental', 9, 18, '3室1厅1卫', 'one', 'east', 23.00, 6800.00, '海淀上地主卧，通勤软件园方便。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000013.jpg', 'https://example.com/h/99000000013_1.jpg', 110100, '北京', 110108, '海淀', '上地佳园', '海淀区上地路13号', 116.3140000, 40.0330000),
(99000000014, 9014, '朝阳传媒大学朝南主卧', 'worry_free_rental', 3, 6, '3室1厅1卫', 'one', 'south', 20.00, 3900.00, '朝阳主卧，朝南，生活便利。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000014.jpg', 'https://example.com/h/99000000014_1.jpg', 110100, '北京', 110105, '朝阳', '传媒大学家园', '朝阳区定福庄路14号', 116.5560000, 39.9130000),
(99000000015, 9015, '朝阳大望路主卧', 'worry_free_rental', 16, 28, '3室1厅1卫', 'one', 'north', 19.00, 5600.00, '朝阳大望路主卧，近商圈，公共厨房。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000015.jpg', 'https://example.com/h/99000000015_1.jpg', 110100, '北京', 110105, '朝阳', '大望路社区', '朝阳区大望路15号', 116.4760000, 39.9080000),
(99000000016, 9016, '朝阳亮马桥朝南主卧', 'worry_free_rental', 20, 30, '3室1厅1卫', 'one', 'south', 26.00, 6100.00, '朝阳亮马桥主卧，朝南，近地铁。', 'aircondition,washer,cook,gas,broadband,heating', 'https://example.com/h/99000000016.jpg', 'https://example.com/h/99000000016_1.jpg', 110100, '北京', 110105, '朝阳', '亮马桥公寓', '朝阳区亮马桥路16号', 116.4700000, 39.9490000),
(99000000017, 9017, '海淀苏州街朝南主卧', 'worry_free_rental', 5, 15, '3室1厅1卫', 'one', 'south', 24.00, 7000.00, '海淀苏州街主卧，朝南，地铁便利。', 'aircondition,washer,broadband,heating', 'https://example.com/h/99000000017.jpg', 'https://example.com/h/99000000017_1.jpg', 110100, '北京', 110108, '海淀', '苏州街社区', '海淀区苏州街17号', 116.3060000, 39.9750000),
(99000000018, 9018, '朝阳太阳宫主卧', 'worry_free_rental', 8, 18, '3室1厅1卫', 'one', 'south', 24.50, 7000.00, '朝阳太阳宫主卧，安静，采光好。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000018.jpg', 'https://example.com/h/99000000018_1.jpg', 110100, '北京', 110105, '朝阳', '太阳宫小区', '朝阳区太阳宫路18号', 116.4480000, 39.9710000),
(99000000019, 9019, '海淀学院路主卧', 'worry_free_rental', 2, 6, '3室1厅1卫', 'one', 'west', 22.00, 4500.00, '海淀学院路主卧，室友少，公共厨房。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000019.jpg', 'https://example.com/h/99000000019_1.jpg', 110100, '北京', 110108, '海淀', '学院路社区', '海淀区学院路19号', 116.3520000, 39.9980000),
(99000000020, 9020, '朝阳青年路朝南主卧', 'worry_free_rental', 18, 26, '3室1厅1卫', 'one', 'south', 23.00, 5200.00, '朝阳青年路主卧，朝南，近地铁。', 'aircondition,washer,cook,gas,broadband,heating', 'https://example.com/h/99000000020.jpg', 'https://example.com/h/99000000020_1.jpg', 110100, '北京', 110105, '朝阳', '青年路社区', '朝阳区青年路20号', 116.5170000, 39.9280000),
(99000000021, 9021, '北京通州低价单间', 'worry_free_rental', 6, 12, '1室1厅1卫', 'one', 'south', 18.00, 2500.00, '北京低价单间，适合预算有限用户。', 'aircondition,washer', 'https://example.com/h/99000000021.jpg', 'https://example.com/h/99000000021_1.jpg', 110100, '北京', 110112, '通州', '梨园小区', '通州区梨园路21号', 116.6570000, 39.8830000),
(99000000022, 9022, '北京昌平便宜主卧', 'worry_free_rental', 7, 18, '3室1厅1卫', 'one', 'south', 21.00, 2800.00, '昌平主卧，价格低，近地铁。', 'aircondition,washer,broadband,heating', 'https://example.com/h/99000000022.jpg', 'https://example.com/h/99000000022_1.jpg', 110100, '北京', 110114, '昌平', '回龙观社区', '昌平区回龙观路22号', 116.3390000, 40.0700000),
(99000000023, 9023, '海淀清河低价主卧', 'worry_free_rental', 5, 18, '3室1厅1卫', 'one', 'south', 20.00, 3000.00, '海淀清河主卧，价格低，交通方便。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000023.jpg', 'https://example.com/h/99000000023_1.jpg', 110100, '北京', 110108, '海淀', '清河小区', '海淀区清河路23号', 116.3420000, 40.0330000),
(99000000024, 9024, '北京朝阳整租两居室', 'whole_rent', 14, 25, '2室1厅1卫', 'two', 'south', 75.00, 10500.00, '朝阳两居室整租，空间大，适合家庭。', 'cook,gas,aircondition,icebox,washer', 'https://example.com/h/99000000024.jpg', 'https://example.com/h/99000000024_1.jpg', 110100, '北京', 110105, '朝阳', '朝阳公园社区', '朝阳区朝阳公园路24号', 116.4820000, 39.9450000),
(99000000025, 9025, '北京海淀整租两居室', 'whole_rent', 10, 22, '2室1厅1卫', 'two', 'south', 70.00, 11000.00, '海淀两居室整租，近学校和地铁。', 'cook,gas,aircondition,icebox,washer,broadband,heating', 'https://example.com/h/99000000025.jpg', 'https://example.com/h/99000000025_1.jpg', 110100, '北京', 110108, '海淀', '万柳社区', '海淀区万柳路25号', 116.2940000, 39.9650000),
(99000000026, 9026, '朝阳CBD主卧独卫', 'worry_free_rental', 23, 32, '3室1厅1卫', 'one', 'south', 27.00, 7600.00, '朝阳CBD主卧，带独卫，楼层高。', 'toilet,aircondition,washer,cook,gas', 'https://example.com/h/99000000026.jpg', 'https://example.com/h/99000000026_1.jpg', 110100, '北京', 110105, '朝阳', 'CBD公寓', '朝阳区建国门外大街26号', 116.4580000, 39.9130000),
(99000000027, 9027, '海淀西二旗主卧近地铁', 'worry_free_rental', 17, 28, '3室1厅1卫', 'one', 'south', 25.00, 7400.00, '海淀西二旗主卧，近地铁和产业园。', 'aircondition,washer,cook,gas,broadband,heating', 'https://example.com/h/99000000027.jpg', 'https://example.com/h/99000000027_1.jpg', 110100, '北京', 110108, '海淀', '西二旗社区', '海淀区西二旗路27号', 116.3060000, 40.0520000),
(99000000028, 9028, '浦东张江两居室近地铁', 'whole_rent', 12, 24, '2室1厅1卫', 'two', 'south', 80.00, 9500.00, '上海浦东张江两居室，近地铁，适合家庭。', 'cook,gas,aircondition,icebox,washer,broadband,heating', 'https://example.com/h/99000000028.jpg', 'https://example.com/h/99000000028_1.jpg', 310100, '上海', 310115, '浦东', '张江社区', '浦东新区张江路28号', 121.6000000, 31.2050000),
(99000000029, 9029, '朝阳常营主卧带独卫', 'worry_free_rental', 6, 18, '3室1厅1卫', 'one', 'south', 23.50, 5000.00, '朝阳常营主卧，带独卫，地铁方便。', 'toilet,aircondition,washer,cook,gas,broadband,heating', 'https://example.com/h/99000000029.jpg', 'https://example.com/h/99000000029_1.jpg', 110100, '北京', 110105, '朝阳', '常营家园', '朝阳区常营路29号', 116.5920000, 39.9260000),
(99000000030, 9030, '海淀人民大学朝南房源', 'worry_free_rental', 9, 18, '3室1厅1卫', 'one', 'south', 18.50, 5800.00, '海淀人民大学附近房源，朝南，公共厨房。', 'aircondition,washer,cook,gas', 'https://example.com/h/99000000030.jpg', 'https://example.com/h/99000000030_1.jpg', 110100, '北京', 110108, '海淀', '人大社区', '海淀区中关村大街30号', 116.3200000, 39.9670000);

COMMIT;

SELECT COUNT(*) AS seeded_houses
FROM `houses`
WHERE `id` BETWEEN 99000000001 AND 99000000030;
