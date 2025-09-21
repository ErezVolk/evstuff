#!/bin/sh

DOWNLOADED="Downloaded File.mp3"
ARTIST="Artist"
ALBUM="Album"
YEAR=1984

FOLDER="$ARTIST - $ALBUM"
track() {
    mp3splt -o "$FOLDER/$1 - $2" -g "[@a=$ARTIST,@b=$ALBUM,@t=$2,@y=$YEAR,@g=8,@n=$1]" "$DOWNLOADED" $(echo $3 |tr : .) $(echo $4 |tr : .)
}

rm -Rfv "$FOLDER"
track 1 "Song" 00:00 04:57
open "$FOLDER"
