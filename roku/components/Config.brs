
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
{
    Title: "Channel 14"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/now14.png"
    Stream: "https://splittv.ch20-cdnwiz.com/hls/live_360/index.m3u8"
}
{
    Title: "Channel 24"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/music24.png"
    Stream: "https://mako-streaming.akamaized.net/direct/hls/live/2035340/ch24/index_2200.m3u8"
}
{
    Title: "Knesset"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/knesset.png"
    Stream: "https://contact.gostreaming.tv/Knesset/myStream/playlist.m3u8"
}
{
    Title: "NHK World"
    streamFormat: "hls"
    Stream: "https://nhkwlive-xjp.akamaized.net/hls/live/2003458/nhkwlive-xjp-en/index_1M.m3u8"
}
{
    Title: "103 FM"
    streamFormat: "mp4"
    Stream: "https://cdn.cybercdn.live/103FM/Live/icecast.audio"
}
    
    
    
'##### Make sure all Channel content is above this line #####    
    ] 
    return arr
End Function
