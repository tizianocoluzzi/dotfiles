import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    PanelWindow {
        id: board

        // Desktop background layer
        WlrLayershell.layer: WlrLayer.Bottom
        exclusionMode: ExclusionMode.Ignore

        anchors {
            top: true
            left: true
        }

        margins {
            top: 80
            left: 50
        }

        implicitWidth: 1050
        implicitHeight: 650

        color: "transparent"

        // Read-only desktop element
        mask: Region {}

        // Read directly from Obsidian
        FileView {
            id: markdown

            path: Quickshell.env("HOME")
                + "/Documents/Prova/1-RawNotes/SpaceTeam/TODO.md"

            watchChanges: true
            onFileChanged: reload()
        }

        // Parse Markdown into columns
        function parseKanban(content) {
            let columns = []
            let current = null

            for (let line of content.split("\n")) {

                // Markdown headings become columns
                if (line.startsWith("## ")) {
                    current = {
                        title: line.substring(3).trim(),
                        tasks: []
                    }

                    columns.push(current)
                    continue
                }

                // Markdown checkboxes become cards
                let match = line.match(
                    /^\s*[-*+] \[([ xX])\] (.+)$/
                )

                if (match && current !== null) {
                    current.tasks.push({
                        done: match[1].toLowerCase() === "x",
                        text: match[2]
                    })
                }
            }

            return columns
        }

        property var columns: parseKanban(markdown.text())

        Rectangle {
            anchors.fill: parent

            radius: 20
            color: "#CC181825"

            Column {
                anchors.fill: parent
                anchors.margins: 25
                spacing: 24

                Text {
                    text: "PROJECT BOARD"

                    color: "#CDD6F4"
                    font.pixelSize: 26
                    font.bold: true
                }

                Row {
                    spacing: 18

                    Repeater {
                        model: board.columns

                        delegate: Rectangle {
                            id: kanbanColumn

                            required property var modelData

                            width: 315
                            height: 540

                            radius: 12
                            color: "#AA313244"

                            Column {
                                anchors.fill: parent
                                anchors.margins: 15
                                spacing: 15

                                // Column title
                                Text {
                                    text: kanbanColumn.modelData.title

                                    color: "#CBA6F7"
                                    font.pixelSize: 18
                                    font.bold: true
                                }

                                Rectangle {
                                    width: parent.width
                                    height: 1
                                    color: "#585B70"
                                }

                                // Scrollable task cards
                                Flickable {
                                    width: parent.width
                                    height: parent.height - 65

                                    contentHeight: cards.height
                                    clip: true

                                    Column {
                                        id: cards

                                        width: parent.width
                                        spacing: 10

                                        Repeater {
                                            model: kanbanColumn.modelData.tasks

                                            delegate: Rectangle {
                                                required property var modelData

                                                width: cards.width
                                                height: taskText.implicitHeight + 28

                                                radius: 8
                                                color: "#45475A"

                                                Text {
                                                    id: taskText

                                                    anchors {
                                                        left: parent.left
                                                        right: parent.right
                                                        verticalCenter: parent.verticalCenter
                                                        margins: 14
                                                    }

                                                    text: (
                                                        modelData.done ? "✓ " : "○ "
                                                    ) + modelData.text

                                                    color: modelData.done
                                                        ? "#A6E3A1"
                                                        : "#CDD6F4"

                                                    font.pixelSize: 15
                                                    wrapMode: Text.WordWrap
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
