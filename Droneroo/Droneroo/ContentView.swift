// Created by Erez Volk.

import SwiftUI
import Combine


struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @State private var delta = 0
    @State private var toggle = false
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Text(audioManager.previousNoteName)
                    .encircle(
                        diameter: 80,
                        textColor: audioManager.isForward ? .otherCircleText : .circleText,
                        circleColor: audioManager.isForward ? .otherCircleBack : .circleBack)
                    .onTapGesture { delta += 1 }
                
                Toggle(audioManager.currentNoteName, isOn: $audioManager.isPlaying)
                    .focusable()
                    .focused($focused)
                    .onAppear {
                        focused = true
                    }
                    .onKeyPress(keys: [.leftArrow]) { _ in
                        delta -= 1
                        return .handled
                    }
                    .onKeyPress(keys: [.rightArrow]) { _ in
                        delta += 1
                        return .handled
                    }
                    .onChange(of: delta) {
                        if delta != 0 { audioManager.changeDrone(delta) }
                        delta = 0
                    }
                    .onKeyPress(keys: [.space]) { _ in
                        toggle = !toggle
                        return .handled
                    }
                    .onTapGesture {
                        toggle = !toggle
                    }
                    .onChange(of: toggle) {
                        if toggle {audioManager.toggleDrone()}
                        toggle = false
                    }
                    .toggleStyle(EncircledToggleStyle())
                
                Text(audioManager.nextNoteName)
                    .encircle(diameter: 104,
                              textColor: audioManager.isForward ? .circleText : .otherCircleText,
                              circleColor: audioManager.isForward ? .circleBack : .otherCircleBack)
                    .onTapGesture { delta -= 1 }
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

                Image(systemName: audioManager.isForward ? "chevron.right.dotted.chevron.right" : "chevron.left.chevron.left.dotted")
                    .encircle(diameter: 24, shadowRadius: 0, textColor: .directionText, circleColor: .directionBack, textFont: .body)
                    .onTapGesture { audioManager.flipDirection() }
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
        .containerRelativeFrame([.horizontal, .vertical])
        .background(Color.dronerooBack)
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
