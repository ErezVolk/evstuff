// Created by Erez Volk.

import SwiftUI
import Combine


struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @State private var delta = 0
    @State private var onOff = false
    @State private var alpha = 1
    @FocusState private var focused: Bool
#if os(macOS)
    private let signpostDiameter = 32
#else
    private let signpostDiameter = 40
#endif

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Text(audioManager.previousNoteName)
                    .encircle(
                        diameter: 80,
                        textColor: alpha > 0 ? .otherCircleText : .circleText,
                        circleColor: alpha > 0 ? .otherCircleBack : .circleBack)
                    .onTapGesture { delta -= 1 }
                
                Toggle(audioManager.currentNoteName, isOn: $audioManager.isPlaying)
                    .focusable()
                    .focused($focused)
                    .onAppear {
                        focused = true
                    }
                    .onKeyPress(keys: [.leftArrow]) { _ in
                        delta -= alpha
                        return .handled
                    }
                    .onKeyPress(keys: [.rightArrow]) { _ in
                        delta += alpha
                        return .handled
                    }
                    .onChange(of: delta) {
                        if delta != 0 { audioManager.changeDrone(delta) }
                        delta = 0
                    }
                    .onKeyPress(keys: [.space]) { _ in
                        onOff = !onOff
                        return .handled
                    }
                    .onTapGesture {
                        onOff = !onOff
                    }
                    .onChange(of: onOff) {
                        if onOff {audioManager.toggleDrone()}
                        onOff = false
                    }
                    .toggleStyle(EncircledToggleStyle())
                
                Text(audioManager.nextNoteName)
                    .encircle(diameter: 80,
                              textColor: alpha > 0 ? .circleText : .otherCircleText,
                              circleColor: alpha > 0 ? .circleBack : .otherCircleBack)
                    .onTapGesture { delta += 1 }
            }

            HStack {
                Picker("", selection: $selectedSequence) {
                    ForEach(SequenceType.allCases) { sequence in
                        Text(sequence.rawValue).tag(sequence)
                    }
                }
                .fixedSize()
                .onChange(of: selectedSequence) {
                    audioManager.sequenceType = selectedSequence
                    audioManager.loadSequence()
                }

                Image(systemName: alpha > 0 ? "signpost.right.fill" : "signpost.left.fill")
                    .encircle(diameter: signpostDiameter, textColor: .directionText, circleColor: .directionBack, textFont: .body)
                    .onTapGesture { alpha = -alpha }
            }

            // Instrument
            HStack {
#if os(macOS)
                Button("Load SoundFont") {
                    let panel = NSOpenPanel()
                    panel.allowsMultipleSelection = false
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK {
                        audioManager.loadInstrument(panel.url!)
                    }
                }
#endif
                Button("Default") {
                    audioManager.loadInstrument()
                }
                Button("Reset") {
                    audioManager.resetInstrument()
                }
                Text(audioManager.instrument)
                    .monospaced()
            }
        }
#if os(iOS)
        .containerRelativeFrame([.horizontal, .vertical])
        .background(Color.dronerooBack)
#endif
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
