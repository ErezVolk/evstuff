// Created by Erez Volk.

import SwiftUI
import Combine

struct Encircled: ViewModifier {
    let diameter: CGFloat
    
    func body(content: Content) -> some View {
        return Circle()
            .frame(width: diameter, height: diameter)
            .overlay { content }
    }
}

extension View {
    func encircle(big: Bool = false, shadowRadius: CGFloat = 3, circleColor: Color = .gray) -> some View {
        font(.system(size: big ? 32 : 24))
            .foregroundColor(.white)
            .modifier(Encircled(diameter: big ? 120 : 80))
            .shadow(radius: shadowRadius)
            .foregroundColor(circleColor)
    }
}

struct CircledToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .encircle(big: true, shadowRadius: configuration.isOn ? 10: 3, circleColor: configuration.isOn ? Color.black : Color.gray)
            .onTapGesture { configuration.isOn.toggle() }
    }
}

extension ToggleStyle where Self == CircledToggleStyle {
    static var encircled: CircledToggleStyle { .init() }
}

struct ContentView: View {
    @StateObject private var audioManager = AudioManager()
    @State private var selectedSequence: SequenceType = .circleOfFourth
    @State private var selectedOrder: SequenceOrder = .forward
    @State private var delta = 0
    @State private var toggle = false
    @FocusState private var focused: Bool

    /// Convert a `SequenceOrder` constant to the SF shape we want for it
    private func orderShape(_ order: SequenceOrder) -> String {
        switch order {
        case .forward: return "arrow.forward"
        case .backward: return "arrow.backward"
        }
    }

    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Text(audioManager.previousNoteName)
                    .encircle()
                
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
                    .onChange(of: toggle) {
                        if toggle {audioManager.toggleDrone()}
                        toggle = false
                    }
                    .toggleStyle(.encircled)
                
                Text(audioManager.nextNoteName)
                    .encircle()
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
                Picker("", selection: $selectedOrder) {
                    ForEach(SequenceOrder.allCases) { order in
                        Image(systemName: orderShape(order)).tag(order)
                    }
                }
                .pickerStyle(PalettePickerStyle())
                .fixedSize()
                .onChange(of: selectedOrder) { audioManager.sequenceOrder = selectedOrder }
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

            // Volume Slider
            VStack {
                HStack {
                    Text("Volume")
                        .font(.headline)
                    Spacer()
                    Text("\(Int(audioManager.volume * 100))%")
                        .font(.subheadline)
                }
                .padding([.leading, .trailing], 40)

                Slider(value: $audioManager.volume, in: 0...1)
                .padding([.leading, .trailing], 40)
            }
        }
        .onAppear {
            audioManager.loadSequence()
        }
    }
}
