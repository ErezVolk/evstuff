
' ********** Copyright 2016 Roku Corp.  All Rights Reserved. **********

Function loadConfig() as Object
    arr = [
'##### Format for inputting stream info #####
'## For each channel, enclose in brackets ## 
'{
'   Title: Channel Title
'   streamFormat: Channel stream type (ex. "hls", "ism", "mp4", etc..)
'   Stream: URL to stream (ex. http://hls.Roku.com/talks/xxx.m3u8)
'}
    
{
    Title: "Kan 11"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/ipbc_tv_11.png"
    Stream: "https://kan11.media.kan.org.il/hls/live/2024514/2024514/source1_2.5k/chunklist.m3u8"
}
'{
'    Title: "Channel 13"
'    streamFormat: "hls"
'    Stream: "https://d18b0e6mopany4.cloudfront.net/out/v1/08bc71cf0a0f4712b6b03c732b0e6d25/index_3.m3u8"
'}
{
    Title: "Channel 14"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/now14.png"
    Stream: "https://n-121-5.il.cdn-redge.media/livehls/oil/ch14/live/ch14/live.livx/playlist.m3u8"
}
'{
'    Title: "Channel 24"
'    streamFormat: "hls"
'    Logo: "https://erezvolk.github.io/iltv/images/posters/music24.png"
'    Stream: "https://mako-streaming.akamaized.net/direct/hls/live/2035340/ch24live/hdntl=exp=1680890588~acl=%2f*~data=hdntl~hmac=402319e58d8e302501cbc19dd231943fbd1b1a07ad763e9adb54c15ad62a9003/video_10801920_p_1.m3u8"
'}
{
    Title: "Kan Hinuhit"
    streamFormat: "hls"
    Stream: "https://kan23.media.kan.org.il/hls/live/2024691/2024691/source1_2.5k/chunklist.m3u8"
}
{
    Title: "Knesset"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/knesset.png"
    Stream: "https://kneset.gostreaming.tv/p2-kneset/_definst_/myStream/playlist.m3u8"
}
{
    Title: "NHK World"
    streamFormat: "hls"
'    Stream: "https://master.nhkworld.jp/nhkworld-tv/playlist/live.m3u8"
    Stream: "https://nhkworld-tv.akamaized.net/hls/live/2115640/nhkworld-tv/index_1M.m3u8"
}
    
    
    
'##### Make sure all Channel content is above this line #####    
    ] 
    return arr
End Function
