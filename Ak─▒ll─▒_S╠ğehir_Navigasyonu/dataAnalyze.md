# GTFS Veri Ozeti (Ilk 20 Satir)

Bu dosya, `akilli_sehir_navigasyon/data/gtfs` altindaki her CSV icin ilk 20 satiri ve verinin neyle ilgili olduguna dair kisa aciklamayi icerir.

## iett_routes.csv

**Konu:** IETT otobus hatlari. Hat kodu/kisa adi, uzun ad, tip ve aciklama gibi bilgiler.


Ilk 20 satir:

```csv
﻿_id;route_id;agency_id;route_short_name;route_long_name;route_type;route_desc;route_code
1;1;1;1;KADIKÖY - KİRAZLITEPE;3;;1_D_D0
2;2;1;1;KADIKÖY - KİRAZLITEPE;3;SAATLER FERAH CADDESİNDEN GİDER.;1_D_D2784
3;3;1;1;KİRAZLITEPE - KADIKÖY;3;;1_G_D0
4;4;1;1;KİRAZLITEPE - KADIKÖY;3;SAATLER FERAH CADDESİNDEN GİDER.;1_G_D2783
5;5;1;1;KİRAZLITEPE - KADIKÖY;3;;1_G_D2900
6;6;1;1;KİRAZLITEPE - KADIKÖY;3;;1_G_D2975
7;7;1;10;BOSTANCI PERONLAR - ÜMRANİYE DEVLET HASTANESİ ACİL;3;;10_D_D0
8;9;1;10;ÜMRANİYE EÄžİTİM ARAŞTIRMA HASTANESİ - BOSTANCI GÖSTERİ MERKEZİ;3;;10_G_D2175
9;10;1;10A;ATAŞEHİR TIP MERKEZİ - ESATPAŞA;3;;10A_D_D0
10;11;1;10A;ATAŞEHİR TIP MERKEZİ - ESATPAŞA;3;;10A_D_D1384
11;12;1;10A;ATAŞEHİR TIP MERKEZİ - ESATPAŞA;3;;10A_D_D2938
12;13;1;10A;ESATPAŞA - ATAŞEHİR TIP MERKEZİ;3;;10A_G_D0
13;14;1;10A;ESATPAŞA - ATAŞEHİR TIP MERKEZİ;3;SEFERLER KARLIDERE CADDESİNDEN HİZMET VERİR.;10A_G_D1385
14;15;1;10A;ESATPAŞA - ATAŞEHİR TIP MERKEZİ;3;;10A_G_D2937
15;16;1;10B;KADIKÖY - KOCAYOL CADDESİ;3;;10B_D_D5187
16;17;1;10B;BOSTANCI - KADIKÖY;3;;10B_G_D5186
17;18;1;10B;BOSTANCI - KOCAYOL CADDESİ;3;;10B_G_D1580
18;19;1;10B;BOSTANCI - KADIKÖY;3;;10B_G_D2056
19;21;1;10E;KADIKÖY - ESATPAŞA;3;;10E_D_D0
```


## iett_stop_times.csv

**Konu:** IETT seferlerinin durak sirasi ve zamanlari. Trip icin durak dizisi ve varis/kalkis saatleri.


Ilk 20 satir:

```csv
trip_id,stop_id,stop_sequence,arrival_time,departure_time,timepoint
446025067,510964,1,06:40:00,06:40:00,1
446025067,510801,2,,,0
446025067,510676,3,,,0
446025067,510643,4,,,0
446025067,510659,5,,,0
446025067,510645,6,,,0
446025067,510647,7,,,0
446025067,510649,8,,,0
446025067,510651,9,,,0
446025067,681278,10,,,0
446025067,681265,11,,,0
446025067,681267,12,,,0
446025067,681269,13,,,0
446025067,681271,14,,,0
446025067,681384,15,,,0
446025067,681380,16,,,0
446025067,681378,17,,,0
446025067,681553,18,,,0
446025067,681633,19,,,0
```


## iett_stops.csv

**Konu:** IETT duraklari. Durak adi, koordinat ve aciklama (yon) bilgisi.


Ilk 20 satir:

```csv
﻿stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,location_type
292235,100001,RIFAT ILGAZ CADDESİ,direction: AVCILAR,41.0191700005564,28.6843529999755,0
292236,100002,RIFAT ILGAZ CADDESİ,direction: BOĞAZKÖY,41.0190470005563,28.6846599999755,0
292237,100011,UZUNYAYLA,direction: AVCILAR,41.0104540005549,28.6886289999758,0
292238,100012,UZUNYAYLA,direction: BOĞAZKÖY,41.010675000555,28.6887509999759,0
292240,100022,OKTAY RIFAT CADDESİ,direction: BOĞAZKÖY,41.004605000554,28.6952349999764,0
5251770,100031,SEBAHATTİN ZAİM İLKOKULU,direction: AVCILAR METROBÜS,41.00506785536913,28.6975877961211,0
292242,100032,SEBAHATTİN ZAİM İLKOKULU,direction: BOĞAZKÖY,41.004503000554,28.6991239999767,0
509457,100071,YEŞİLTEPE,direction: AVCILAR,41.0361650005591,28.7039479999769,0
509458,100072,YEŞİLTEPE,direction: FIRUZKÖY,41.0360930005591,28.7038819999769,0
290916,100081,19 MAYIS CADDESİ,direction: AVCILAR,40.9938510005522,28.6723869999746,0
290917,100082,19 MAYIS CADDESİ,direction: İ.MARMARA EVLERİ,40.9936940005522,28.6722419999746,0
290918,100091,AKASYA ,direction: AVCILAR,40.9864660005511,28.6759869999749,0
290919,100092,AKASYA ,direction: İ.MARMARA EVLERİ,40.9863910005511,28.6758629999749,0
290920,100101,GÜZELYAYLA,direction: AVCILAR,40.9872340005512,28.6802479999753,0
290921,100102,GÜZELYAYLA,direction: İ.MARMARA EVLERİ,40.9871480005512,28.6801259999753,0
290922,100111,BARBAROS CADDESİ ,direction: AVCILAR,40.9833240005506,28.6812219999754,0
290923,100112,BARBAROS CADDESİ,direction: İ.MARMARA EVLERİ,40.985969000551,28.6809359999753,0
290924,100121,BEYLİKDÜZÜ AĞIZ VE DİŞ SAĞLIĞI MERKEZİ,direction: AVCILAR,40.9837090005507,28.6779579999751,0
290908,100122,BEYLİKDÜZÜ AĞIZ VE DİŞ SAĞLIĞI MERKEZİ,direction: İ.MARMARA EVLERİ,40.9838790005498,28.6775169999739,0
```


## iett_trips.csv

**Konu:** IETT seferleri (trip). Hat ile sefer arasindaki baglanti, yon ve servis bilgisi.


Ilk 20 satir:

```csv
﻿_id,trip_id,route_id,service_id,trip_headsign,direction_id
1,446025067,1,6,KİRAZLITEPE,1
2,446025071,2,6,KİRAZLITEPE,1
3,446018023,1,6,KİRAZLITEPE,1
4,446008695,1,6,KİRAZLITEPE,1
5,445928247,1,6,KİRAZLITEPE,1
6,445935507,1,6,KİRAZLITEPE,1
7,445949094,1,6,KİRAZLITEPE,1
8,445966383,1,6,KİRAZLITEPE,1
9,445999459,1,0,KİRAZLITEPE,1
10,446025069,1,0,KİRAZLITEPE,1
11,445995619,1,0,KİRAZLITEPE,1
12,446025073,2,0,KİRAZLITEPE,1
13,446013974,1,0,KİRAZLITEPE,1
14,445933547,1,0,KİRAZLITEPE,1
15,446008487,2,0,KİRAZLITEPE,1
16,445939843,1,0,KİRAZLITEPE,1
17,446025075,2,0,KİRAZLITEPE,1
18,445952454,1,0,KİRAZLITEPE,1
19,445966013,1,0,KİRAZLITEPE,1
```


## routes.csv

**Konu:** Rayli/deniz hatlari (sehir hatlari gibi). Hat kodu, ad, tip ve URL bilgisi.


Ilk 20 satir:

```csv
route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color
28195,6,BSK-HLC,BEŞİKTAŞ - KABATAŞ - KARAKÖY - KASIMPAŞA - SÜTLÜCE - EYÜP,,4,,,
28194,6,KDK-HLC,KADIKÖY - KASIMPAŞA - FENER - SÜTLÜCE - EYÜP,,4,,,
28191,6,ASYN-KCS,Aşiyan - Anadolu Hisarı - Küçüksu Ring,,4,https://www.sehirhatlari.istanbul/tr/seferler/ic-hatlar/istanbul-ici-hatlar/asiyan-anadolu-hisari-kucuksu-ring-hatti-2014,,
7060,6,BOS-KRK-KBTŞ,BOSTANCI - KARAKÖY - KABATAŞ,,4,http://www.sehirhatlari.istanbul/tr/seferler/bostanci-karakoy-6498.html,,
26722,6,BYKADA-HYBADA,HEYBELİADA-BÜYÜKADA,,4,http://www.sehirhatlari.istanbul/tr/seferler/bostanci-adalar-ring-hatti-9504.html,,
26721,6,BOS-ADA_RING,BOSTANCI-ADALAR RING,,4,http://www.sehirhatlari.istanbul/tr/seferler/bostanci-adalar-ring-hatti-9504.html,,
26719,6,BŞK-BYKADA,BEŞİKTAŞ-HEYBELİADA-BÜYÜKADA,,4,http://www.sehirhatlari.istanbul/tr/seferler/besiktas-heybeliada-buyukada-3487.html,,
26718,6,BŞK-ADA_2,BEŞİKTAŞ-KINALIADA-BURGAZADA,,4,http://www.sehirhatlari.istanbul/tr/seferler/besiktas-kinaliada-burgazada-3486.html,,
26717,6,BŞK-ADA,BEŞİKTAŞ-KINALIADA-BURGAZADA,,4,http://www.sehirhatlari.istanbul/tr/seferler/besiktas-kinaliada-burgazada-3486.html,,
26716,6,KBTŞ-EMN-KDK-ADA,KABATAŞ - EMİNÖNÜ - KADIKÖY - ADALAR,,4,http://www.sehirhatlari.istanbul/tr/seferler/kabatas-eminonu-kadikoy-adalar-369.html,,
26715,6,BOS-ADA,BOSTANCI - ADALAR (BÜYÜKADA - HEYBELİADA),,4,http://www.sehirhatlari.istanbul/tr/seferler/bostanci-adalar-370.html,,
2063,6,ÇNGK-iST,ÇENGELKÖY - İSTİNYE,,4,,,
831,6,BĞZ-16,BOĞAZA GİDİŞ,,4,,,
7503,6,BYK-ÜSK,BEYKOZ - ÜSKÜDAR,,4,http://www.sehirhatlari.com.tr/tr/seferler/,,
7496,6,ERGVN,ERGUVAN TURU,,4,http://www.sehirhatlari.com.tr/tr/seferler/,,
7493,6,KISA BĞZ,KISA BOĞAZ TURU,,4,http://www.sehirhatlari.com.tr/tr/seferler/,,
817,6,BĞZ-6,BOĞAZDAN GELİŞ,,4,,,
804,6,BĞZ-23,BOĞAZA GİDİŞ,,4,,,
807,6,BĞZ-17,BOĞAZA GİDİŞ,,4,,,
```


## stop_times.csv

**Konu:** Rayli/deniz seferlerinin durak sirasi ve zamanlari. Trip icin durak dizisi ve varis/kalkis saatleri.


Ilk 20 satir:

```csv
trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled,timepoint
3166693,13:05:00,13:05:15,18910,6,Beşiktaş-Üsküdar ŞH.,0,0,8.925,0
3166693,13:00:00,13:00:15,18918,5,Kabataş ŞH.,0,0,7.394,0
3166693,12:50:00,12:50:15,18920,4,Karaköy ŞH.,0,0,5.115,0
3166693,12:40:00,12:40:15,18943,3,Kasımpaşa ŞH.,0,0,3.261,0
3166693,12:25:00,12:25:15,18930,2,Sütlüce ŞH.,0,0,0.251,0
3166693,12:20:00,12:20:15,18931,1,Eyüp ŞH.,0,0,0.0,0
3166692,12:05:00,12:05:15,18910,6,Beşiktaş-Üsküdar ŞH.,0,0,8.925,0
3166692,12:00:00,12:00:15,18918,5,Kabataş ŞH.,0,0,7.394,0
3166692,11:50:00,11:50:15,18920,4,Karaköy ŞH.,0,0,5.115,0
3166692,11:40:00,11:40:15,18943,3,Kasımpaşa ŞH.,0,0,3.261,0
3166692,11:25:00,11:25:15,18930,2,Sütlüce ŞH.,0,0,0.251,0
3166692,11:20:00,11:20:15,18931,1,Eyüp ŞH.,0,0,0.0,0
3166691,11:05:00,11:05:15,18910,6,Beşiktaş-Üsküdar ŞH.,0,0,8.925,0
3166691,11:00:00,11:00:15,18918,5,Kabataş ŞH.,0,0,7.394,0
3166691,10:50:00,10:50:15,18920,4,Karaköy ŞH.,0,0,5.115,0
3166691,10:40:00,10:40:15,18943,3,Kasımpaşa ŞH.,0,0,3.261,0
3166691,10:25:00,10:25:15,18930,2,Sütlüce ŞH.,0,0,0.251,0
3166691,10:20:00,10:20:15,18931,1,Eyüp ŞH.,0,0,0.0,0
3166688,18:05:00,18:05:15,18910,6,Beşiktaş-Üsküdar ŞH.,0,0,8.925,0
```


## stops.csv

**Konu:** Rayli/deniz duraklari. Durak adi ve koordinat bilgisi.


Ilk 20 satir:

```csv
﻿stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id,stop_url,location_type,parent_station,stop_timezone,wheelchair_boarding
18926,200016,Anadolu Hisarı ŞH.,Anadolu Hisarı ŞH.,41.083287780558,29.0665429954959,,,0,,,0
18917,200001,Çengelköy ŞH.,Çengelköy ŞH.,41.0510321851052,29.0514175572015,,,0,,,0
18939,200327,Kadıköy-Beşiktaş-Adalar ŞH.,Kadıköy-Beşiktaş-Adalar ŞH.,40.9917168827583,29.021731384099,,,0,,,0
18908,200027,Eminönü-Boğaz ŞH.,Eminönü-Boğaz ŞH.,41.0179947226792,28.9740817118888,,,0,,,0
18920,200022,Karaköy ŞH.,Karaköy ŞH.,41.0217608046809,28.9765707068861,,,0,,,0
18910,200048,Beşiktaş-Üsküdar ŞH.,Beşiktaş-Üsküdar ŞH.,41.0410405054671,29.0073618373518,,,0,,,0
18915,200044,Yeni Kadıköy ŞH.,Yeni Kadıköy ŞH.,40.992993378716,29.0227098868733,,,0,,,0
87063,200338,İstinye ŞH.,,41.113481697445,29.0573095161876,,,0,,,1
272185,200345,Aşiyan ŞH,,41.0809508528703,29.0545221783145,,,0,,,0
94867,200340,Eminönü Camlı İskele ŞH.,,41.0182684977867,28.973107711326,,http://www.sehirhatlari.com.tr/,0,,,0
18911,200323,Heybeliada ŞH.,Heybeliada ŞH.,40.8770724216939,29.1020486584472,,,0,,,0
18940,200002,Beşiktaş-Kadıköy ŞH.,Beşiktaş-Kadıköy ŞH.,41.0399527438131,29.0056554003578,,,0,,,0
18927,200043,Kuzguncuk ŞH.,Kuzguncuk ŞH.,41.0369024446068,29.0297691641189,,,0,,,0
18916,200020,Ayvansaray ŞH.,Ayvansaray ŞH.,41.0408057823696,28.9448160080324,,,0,,,0
18918,200052,Kabataş ŞH.,Kabataş ŞH.,41.0337070141002,28.9936013124533,,,0,,,0
18950,200032,Ortaköy ŞH.,Ortaköy ŞH.,41.0471764118418,29.0256855144434,,,0,,,0
18921,200051,Küçüksu ŞH.,Küçüksu ŞH.,41.0791765147275,29.0651156614152,,,0,,,0
18951,200039,Balat ŞH.,Balat ŞH.,41.0348382595107,28.9493324695385,,,0,,,0
18928,200015,Arnavutköy ŞH.,Arnavutköy ŞH.,41.0667778799808,29.0434343511809,,,0,,,0
```


## trips.csv

**Konu:** Rayli/deniz seferleri (trip). Hat ile sefer arasindaki baglanti, yon ve servis bilgisi.


Ilk 20 satir:

```csv
﻿route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible,bikes_allowed
28195,28,3166693,BEŞİKTAŞ,17:20:00,1,,59381,1,1
28195,28,3166692,BEŞİKTAŞ,17:20:00,1,,59381,1,1
28195,28,3166691,BEŞİKTAŞ,17:20:00,1,,59381,1,1
28195,29,3166688,BEŞİKTAŞ,07:20:00,1,,59381,1,1
28195,29,3166689,BEŞİKTAŞ,07:20:00,1,,59381,1,1
28195,29,3166690,BEŞİKTAŞ,07:20:00,1,,59381,1,1
28195,29,3166681,EYÜP,07:15:00,0,,59380,1,1
28195,29,3166680,EYÜP,07:15:00,0,,59380,1,1
28195,29,3166679,EYÜP,07:15:00,0,,59380,1,1
28195,108,3166687,BEŞİKTAŞ,07:20:00,1,,59381,1,1
28195,108,3166686,BEŞİKTAŞ,07:20:00,1,,59381,1,1
28195,108,3166685,BEŞİKTAŞ,BSK-HLC,1,,59381,1,1
28195,28,3166684,EYÜP,19:15:00,0,,59380,1,1
28195,28,3166683,EYÜP,19:15:00,0,,59380,1,1
28195,28,3166682,EYÜP,19:15:00,0,,59380,1,1
28195,108,3166678,EYÜP,07:15:00,0,,59380,1,1
28195,108,3166677,EYÜP,07:15:00,0,,59380,1,1
28195,108,3166676,EYÜP,BSK-HLC,0,,59380,1,1
28194,29,3166713,KADIKÖY,20:10:00,1,,59379,1,1
```
