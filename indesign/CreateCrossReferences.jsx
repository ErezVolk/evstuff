// ex: set et sw=2:
// TODO: Fix unfixing Source
// TODO: Mirror (insert anchored object with same width, require frame style???)
// TODO: Asterisk when spaced (but unruled) ends at top

function cr_main() {
  cr = {
    messages: []
  };
  cr_run(cr);
}

function cr_run(cr) {
  cr_start_counter(cr);
  try {
    cr_get_docs(cr);

    cr_do_destinations(cr);
    cr_do_sources(cr);

    cr_do_continuations(cr);
    cr_do_continuations(cr); // Yes, twice

    cr_do_export(cr);
  } catch(err) {
    cr_log(cr, "Line " + err.line + ": " + err.name + ": " + err.message);
  }
  cr_stop_counter(cr);
}

function cr_get_docs(cr) {
  cr.docs = [];
  var book = undefined;
  try {
    book = app.activeBook;
  } catch(err) {
    // ignore
  }
  if (book != undefined) {
    bcs = book.bookContents;
    for (var i = 0; i < bcs.length; ++ i) {
      bc = bcs[i];
      cr_log(cr, "Opening " + bc.fullName);
      cr.docs.push(app.open(bc.fullName));
      cr_unlog(cr);
    }
  }
  else {
    cr.docs.push(app.activeDocument);
  }
}

function cr_do_destinations(cr) {
  cr.destinations = {};
  for (var i = 0; i < cr.docs.length; ++ i) {
    cr.doc = cr.docs[i];
    cr_doc_remove_destinations(cr);
    cr_doc_do_destinations(cr);
  }
  cr.doc = undefined;
}

function cr_doc_remove_destinations(cr) {
  var removed = 0;
  var destinations = cr.doc.hyperlinkTextDestinations;
  for (var i = destinations.length - 1; i >= 0; -- i) {
    var destination = destinations[i];
    if (destination.label == "cxr") {
      destination.remove()
      removed = removed + 1;
    }
  }
  if (removed > 0)
    cr_log(cr, "Removed " + removed + " destination(s)");
}

function cr_doc_do_destinations(cr) {
  var added = 0;
  for (var i = 0; i < cr.doc.characterStyles.length; ++ i)
    added = added + cr_doc_style_do_destinations(cr, cr.doc.characterStyles[i]);
  if (added > 0)
    cr_log(cr, "Added " + added + " destination(s)");
}

function cr_doc_style_do_destinations(cr, style) {
  if (style.name.indexOf("@Destination@") < 0)
    return 0;

  var added = 0;
  app.findGrepPreferences = NothingEnum.nothing;
  app.findGrepPreferences.findWhat = ".+"; // i.e., no newlines
  app.findGrepPreferences.appliedCharacterStyle = style.name;
  hits = cr.doc.findGrep();
  for (var i = 0; i < hits.length; ++ i) {
    var text = hits[i];
    var name = text.contents;
    if (cr.destinations.hasOwnProperty(name)) {
      cr_log(cr, "Ignoring duplicate: \"" + name + "\" is " + cr.destinations[name].toSource());
    } else {
      cr_log(cr, "Creating destination \"" + name+ "\"");
      cr.destinations[name] = cr.doc.hyperlinkTextDestinations.add(text, {label: "cxr"})
      cr_unlog(cr);
      added = added + 1;
    }
  }
  app.findGrepPreferences = NothingEnum.nothing;
  return added;
}

function cr_do_sources(cr) {
  for (var i = 0; i < cr.docs.length; ++ i) {
    cr.doc = cr.docs[i];
    cr_doc_undo_sources(cr);
    cr_doc_redo_sources(cr);
  }
  cr.doc = undefined;
}

function cr_doc_undo_sources(cr) {
  var sources = cr.doc.crossReferenceSources;
  var removed = 0;
  for (var i = sources.length - 1; i >= 0; -- i) {
    var source = sources[i];
    if (source.label.substr(0, 4) == "cxr:") {
      source.sourceText.contents = source.label.substr(4);
      source.remove();
      removed = removed + 1;
    }
  }
  if (removed > 0)
    cr_log(cr, "Undid " + removed + " source(s)");
}

function cr_doc_redo_sources(cr) {
  cr.source_style = cr.doc.crossReferenceFormats.itemByName("Bare Page Number");
  if (!cr.source_style.isValid) {
    cr.source_style = cr.doc.crossReferenceSources.add("Bare Page Number");
    cr.source_style.buildingBlocks.add(BuildingBlockTypes.PAGE_NUMBER_BUILDING_BLOCK);
  }

  var added = 0;
  for (var i = 0; i < cr.doc.characterStyles.length; ++ i)
    added = added + cr_doc_style_redo_sources(cr, cr.doc.characterStyles[i]);
  if (added > 0)
    cr_log(cr, "Added " + added + " source(s)");
}

function cr_doc_style_redo_sources(cr, style) {
  if (style.name.indexOf("@Source@") < 0)
    return 0;

  var added = 0;
  app.findGrepPreferences = NothingEnum.nothing;
  app.findGrepPreferences.findWhat = ".+"; // i.e., no newlines
  app.findGrepPreferences.appliedCharacterStyle = style.name;
  hits = cr.doc.findGrep();
  for (var i = 0; i < hits.length; ++ i) {
    var text = hits[i];
    var contents = text.contents;
    if (contents[0] != "=") {
      cr_log(cr, "Ignoring malformed source: " + contents);
      continue;
    }

    var name = contents.substr(1);
    if (!cr.destinations.hasOwnProperty(name)) {
      cr_log(cr, "Ignoring unknown destination: " + contents);
      continue;
    }

    cr_log(cr, "Creating source \"" + name + "\"");
    source = cr.doc.crossReferenceSources.add(text, cr.source_style, {label: "cxr:" + contents})
    cr.doc.hyperlinks.add(source, cr.destinations[name], {label: "cxr"});
    cr_unlog(cr);
    added = added + 1;
  }
  app.findGrepPreferences = NothingEnum.nothing;
  return added;
}

function cr_do_continuations(cr) {
  for (var i = 0; i < cr.docs.length; ++ i) {
    cr.doc = cr.docs[i];
    for (var j = 0; j < cr.doc.paragraphStyles.length; ++ j) {
      var style = cr.doc.paragraphStyles[j];
      if (style.name.indexOf("@Continuation@") < 0) {
        continue;
      }

      app.findGrepPreferences = NothingEnum.nothing;
      app.findGrepPreferences.findWhat = "^";
      app.findGrepPreferences.appliedParagraphStyle = style.name;
      var hits = cr.doc.findGrep();
      app.findGrepPreferences = NothingEnum.nothing;

      var prefs = cr.doc.viewPreferences;
      var oldUnits = prefs.horizontalMeasurementUnits;
      prefs.horizontalMeasurementUnits = MeasurementUnits.points;

      app.findGrepPreferences = NothingEnum.nothing;
      app.findGrepPreferences.findWhat = "^\\s*";
      app.changeGrepPreferences = NothingEnum.nothing;
      app.changeGrepPreferences.changeTo = "";

      for (var i = 0; i < hits.length; ++ i) {
        var hit = hits[i];
        var currPara = hit.paragraphs[0];
        var prevChar = hit.parent.characters.item(currPara.index - 2);

        currPara.changeGrep();

        currPara.firstLineIndent = 0;
        currPara.firstLineIndent = Math.abs(prevChar.endHorizontalOffset - currPara.horizontalOffset);
      }

      app.findGrepPreferences = NothingEnum.nothing;
      app.changeGrepPreferences = NothingEnum.nothing;

      prefs.horizontalMeasurementUnits = oldUnits;
    }
  }
}

function cr_do_export(cr) {
  for (var i = 0; i < cr.docs.length; ++ i) {
    var doc = cr.docs[i];
    var path = File(doc.fullName + ".idml")
    cr_log(cr, "Writing \"" + path.name + "\"");
    doc.exportFile(ExportFormat.INDESIGN_MARKUP, path)
  }
}

function cr_start_counter(cr) {
  cr.start_ms = new Date().valueOf();
}

function cr_stop_counter(cr) {
  end_ms = new Date().valueOf();
  elapsed = (end_ms - cr.start_ms) / 1000.0;

  cr.messages.unshift("Done in " + String(elapsed) + " Sec.");
  alert(cr.messages.join('\n'));
}

function cr_doc_log(cr, msg) {
  cr_log(cr.doc.name + ": " + msg);
}

function cr_log(cr, msg) {
  if (cr.doc != undefined)
    msg = cr.doc.name + ": " + msg;
  cr.messages.push(msg);
}

function cr_unlog(cr) {
  cr.messages.pop();
}

cr_main();

// TODO: Collect sources by styles and covert
// Old source format (note name/label)
// appliedFormat:
//     name: Bare Page Number
//     appliedCharacterStyle: null
//     id: 745387
//     label: 
//     isValid: true
//     parent: [object Document]
//     index: 9
//     properties: [object Object]
//     events: [object Events]
//     eventListeners: [object EventListeners]
//     buildingBlocks: [object BuildingBlocks]
//     isValid: true
// hidden: false
// name: s-8-מפתח ד׳
// sourceText: [object Character]
// appliedCharacterStyle: null
// id: 1027657
// label: s-8-מפתח ד׳
// isValid: true
// parent: [object Document]
// index: 0
// properties: [object Object]
// events: [object Events]
// eventListeners: [object EventListeners]
// isValid: true

