
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
    Stream: "https://kan11.media.kan.org.il/hls/live/2024514-b/2024514/source1_2.5k/chunklist.m3u8"
}
{
    Title: "Keshet 12"
    streamFormat: "hls"
    Logo: "pkg:/images/kehet12.png"
    Stream: "https://mako-streaming.akamaized.net/direct/hls/live/2033791/k12dvr/hdntl=exp=1654539318~acl=%2f*~data=hdntl~hmac=bffb1d0c9a235e86ed789d8b524cf5eff5af44bdccd6c6e3f5d53f7ea0866883/index_550.m3u8"
}
{
    Title: "Reshet 13"
    streamFormat: "hls"
    Logo: "https://erezvolk.github.io/iltv/images/posters/reshet_13.png"
    Stream: "https://d18b0e6mopany4.cloudfront.net/out/v1/08bc71cf0a0f4712b6b03c732b0e6d25/index_3.m3u8"
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
    
    
    
'##### Make sure all Channel content is above this line #####    
    ] 
    return arr
End Function
