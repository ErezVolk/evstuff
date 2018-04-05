// ex: set et sw=2:

// TODO: This pseudo-object isn't nice
// TODO: Multiple main stories are a no-no
// TODO: Split (and unsplit!) frames on specific styles
// TODO: Maybe do the start of line trick?
// TODO: Remove unused imported styles
// TODO: Status notification
// TODO: Change "old load" checkbox to radio
// TODO: Save settings in a variable
// TODO: Offer the precooked searches!
// TODO: Proper master page fixer
// TODO: Index stuff
// TODO: Clear (or do a story break) after "EREZ EREZ"

function Reimporter() {
  this.doc = app.activeDocument;
  this.reflow_changed = false;
}

Reimporter.prototype.run = function() {
  this.analyze();

  if (!this.get_options())
    return;

  if (this.uig_import.checkedState)
    if (!this.get_importee())
      return;

  this.start_counter();
  this.disable_grep();
  this.disable_reflow();
  if (this.uig_pre.checkedState) {
    this.pre_remaster();
    this.pre_clear();
  }
  if (this.uig_import.checkedState) {
    this.do_import();
  }
  if (this.uig_post.checkedState) {
    this.post_clear_overrides();
    this.reset_searches();
    this.post_fix_spaces();
    this.post_fix_dashes();
    this.post_remove_footnote_whitespace();
    this.post_fully_justify();
    this.restore_reflow();
    this.post_fix_masters();
    this.post_update_toc();
  }
  this.enable_grep();
  this.restore_reflow();
  this.stop_counter();
};

Reimporter.prototype.start_counter = function() {
  this.start_ms = new Date().valueOf();
}

Reimporter.prototype.stop_counter = function() {
  end_ms = new Date().valueOf();
  elapsed = (end_ms - this.start_ms) / 1000.0;
  alert("The whole thing took " + String(elapsed) + " Sec.");
}

Reimporter.prototype.analyze = function() {
  var vars = this.doc.textVariables;
  this.var_saved = null;
  this.str_saved = null;

  for (var i = 0; i < vars.length; ++ i) {
    var cur = vars[i]
    if (cur.variableType == VariableTypes.CUSTOM_TEXT_TYPE && cur.name == "Imported From") {
      this.var_saved = cur;
      this.str_saved = cur.variableOptions.contents;
      break;
    }
  }

  var stories = this.doc.stories;
  this.have_toc = false;
  if (this.doc.tocStyles.length > 1) {
    this.toc_styles = this.doc.tocStyles.everyItem().name;
    this.toc_styles.shift();
    for (var i = 0; i < stories.length && !this.have_toc; ++ i) {
      this.have_toc = (stories[i].storyType == StoryTypes.TOC_STORY);
    }
  }
}

Reimporter.prototype.get_options = function() {
  var dlg = app.dialogs.add({name: "ReImport Options"});
  with (dlg) {
    with (dialogColumns.add()) {
      with (this.uig_pre = enablingGroups.add({staticLabel: "Pre-Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          this.ui_pre_remaster =
            checkboxControls.add({
              staticLabel: "Reset all master pages",
              checkedState: true
            });
          this.ui_pre_clear =
            checkboxControls.add({
              staticLabel: "Remove all text",
              checkedState: true
            });
        }
      }

      with (this.uig_import = enablingGroups.add({staticLabel: "Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          if (this.str_saved) {
            this.ui_same_importee = checkboxControls.add({
              staticLabel: "Reload " + String(this.str_saved),
              checkedState: true
            });
          }
          this.ui_import_options = checkboxControls.add({
            staticLabel: "Show import options",
            checkedState: true
          });
        }
      }

      with (this.uig_post = enablingGroups.add({staticLabel: "Post-Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          this.ui_post_clear_overrides =
            checkboxControls.add({
              staticLabel: "Clear all imported style overrides",
              checkedState: true
            });
          this.ui_post_fix_spaces =
            checkboxControls.add({
              staticLabel: "Eliminate multiple spaces",
              checkedState: true
            });
          this.ui_post_fix_dashes =
            checkboxControls.add({
              staticLabel: "Fix spacing around dashes",
              checkedState: true
            });
          this.ui_post_remove_footnote_whitespace =
            checkboxControls.add({
              staticLabel: "Remove leading whitespace in footnotes",
              checkedState: true
            });
          this.ui_post_fully_justify =
            checkboxControls.add({
              staticLabel: "Fix to full justification",
              checkedState: true
            });
          this.ui_post_fix_masters =
            checkboxControls.add({
              staticLabel: "Fix master pages",
              checkedState: true
            });
          if (this.have_toc) {
            this.ui_post_update_toc =
              checkboxControls.add({
                staticLabel: "Update TOC",
                checkedState: true
              });
            this.ui_post_toc_style = dropdowns.add({
              stringList: this.toc_styles,
              selectedIndex: 0
            });
          }
        }
      }

      with (borderPanels.add()) {
        with (dialogColumns.add() ) {
          staticTexts.add({staticLabel: "Default Master:"});
          staticTexts.add({staticLabel: "Headless Master:"});
        }
        with (dialogColumns.add()) {
          var masters = this.doc.masterSpreads.everyItem().name;
          this.ui_a_master = dropdowns.add({stringList: masters, selectedIndex: 0});
          this.ui_b_master = dropdowns.add({stringList: masters, selectedIndex: masters.length - 1});
        }
      }

      with (checkboxControls) {
        with (dialogColumns.add()) {
          this.ui_disable_grep = add({
            staticLabel: "Disable GREP styles while working",
            checkedState: true
          });
          this.ui_disable_reflow = add({
            staticLabel: "Disable smart reflow when applicable",
            checkedState: true
          });
        }
      }
    }
  }
  if (!dlg.show()) {
    dlg.destroy();
    return false;
  }

  this.a_master = this.doc.masterSpreads.itemByName(masters[this.ui_a_master.selectedIndex]);
  this.b_master = this.doc.masterSpreads.itemByName(masters[this.ui_b_master.selectedIndex]);
  return true;
}

Reimporter.prototype.get_importee = function() {
  if (this.str_saved && this.ui_same_importee.checkedState)
    this.importee = this.str_saved;
  else
    this.importee = File.openDialog("Choose your importee", this.filter_files)
  return this.importee;
};

Reimporter.prototype.filter_files = function(file) {
  if (file.constructor.name == "Folder") {
    return true;
  }
  if (file.name.match(/\.(docx?|txt|idtt)$/)) {
    return true;
  }
  return false;
};

Reimporter.prototype.pre_remaster = function() {
  if (!this.ui_pre_remaster.checkedState)
    return;
  this.doc.pages.everyItem().appliedMaster = this.a_master;
};

Reimporter.prototype.pre_clear = function() {
  if (!this.ui_pre_clear.checkedState)
    return;
  var page = this.doc.pages[0];
  this.main_frame(page).parentStory.contents = "";
  //this.override_all_master_page_items(page);
};

Reimporter.prototype.override_all_master_page_items = function(page) {
  for (var i = 0; i < page.masterPageItems.length; ++ i) {
    mpi = page.masterPageItems[i];
    try {
      if (mpi.allowOverrides) {
        mpi.override(page);
      }
    } catch (e) {
    }
  }
};

Reimporter.prototype.do_import = function() {
  var page = this.doc.pages[0];
  var frame = this.main_frame(page);
  try {
    frame.place(this.importee, this.ui_import_options.checkedState);
  } catch (e) {
    alert("Note: Import failed(?)\n" + e);
  }
  if (!this.var_saved)
    this.var_saved = this.doc.textVariables.add({
      name: "Imported From",
      variableType: VariableTypes.CUSTOM_TEXT_TYPE
    });
  this.var_saved.variableOptions.contents = this.importee;
};

Reimporter.prototype.post_clear_overrides = function() {
  if (!this.ui_post_clear_overrides.checkedState)
    return;
  this.doc.stories.everyItem().clearOverrides();
  try {
    this.doc.stories.everyItem().footnotes.everyItem().texts.everyItem().clearOverrides();
  }
  catch (e) {
  }
};

Reimporter.prototype.post_fix_spaces = function() {
  if (!this.ui_post_fix_spaces.checkedState)
    return;

  // Multiple Space to Single Space
  this.change_grep("[~m~>~f~|~S~s~<~/~.~3~4~% ]{2,}", "\\s");

  // No whitespace at the end of paragraphs (doesn't work!?)
  this.change_grep("\\s+$", "");
};

Reimporter.prototype.post_fix_dashes = function() {
  if (!this.ui_post_fix_dashes.checkedState)
    return;

  this.change_grep("[ ~<]+~=[ ~k~<]+", "~<~=~k~<");
};

Reimporter.prototype.post_remove_footnote_whitespace = function() {
  if (!this.ui_post_remove_footnote_whitespace.checkedState)
    return;

  app.findGrepPreferences.findWhat = "(?<=^~F\\t) +";
  app.changeGrepPreferences.changeTo = "";
  try {
    this.doc.stories.everyItem().footnotes.everyItem().texts.everyItem()
      .changeGrep();
  }
  catch (e) {
  }
};

Reimporter.prototype.post_fully_justify = function() {
  if (!this.ui_post_fully_justify.checkedState)
    return;

  var page = this.doc.pages[0];
  var frame = page.textFrames[0];
  var story = frame.parentStory;
  var paragraphs = story.paragraphs;

  var prefs = this.doc.viewPreferences;
  var oldUnits = prefs.horizontalMeasurementUnits;
  prefs.horizontalMeasurementUnits = MeasurementUnits.pixels;

  for (var i = 0; i < paragraphs.count(); ++ i) {
    this.fully_justify(paragraphs[i]);
  }

  prefs.horizontalMeasurementUnits = oldUnits;
};

Reimporter.prototype.fully_justify = function(paragraph) {
  if (paragraph.paragraphDirection != ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION) {
    return;
  }

  var justification = paragraph.justification;
  if (justification != Justification.FULLY_JUSTIFIED && justification != Justification.RIGHT_JUSTIFIED) {
    return;
  }

  var lines = paragraph.lines;
  var numLines = lines.count()
  var lastLine = lines.lastItem();
  var lastLineFrame = lastLine.parentTextFrames[0];
  if (lastLineFrame == undefined) {
    return;
  }

  var lastChar = lastLine.characters.lastItem();
  if (lastChar == '\n') {
    lastChar = lastLine.characters[lastLine.characters.count() - 2];
  }

  var fully = null;
  var right = null;

  if (justification == Justification.FULLY_JUSTIFIED) {
    // Was fully justified, we know the margin
    fully = lastChar.endHorizontalOffset;
    paragraph.justification = Justification.RIGHT_JUSTIFIED;
    right = lastChar.endHorizontalOffset;
  } else if (lines.count() > 1) {
    // Just compare with ante line
    right = lastChar.endHorizontalOffset;
    var anteLine = lines[numLines - 2];
    fully = anteLine.characters.lastItem().endHorizontalOffset;

    var anteLineFrame = anteLine.parentTextFrames[0];

    if (anteLineFrame != lastLineFrame) {
      fully -= anteLineFrame.parentPage.bounds[1];
      fully += lastLineFrame.parentPage.bounds[1];
    }
  } else {
    // Align to check
    right = lastChar.endHorizontalOffset;
    paragraph.justification = Justification.FULLY_JUSTIFIED;
    fully = lastChar.endHorizontalOffset;
  }

  var gap = right - fully;
  var fudge = lastChar.pointSize / 2;

  if (gap < fudge && gap > -fudge) {
    paragraph.justification = Justification.FULLY_JUSTIFIED;
  } else {
    paragraph.justification = Justification.RIGHT_JUSTIFIED;
  }
}

Reimporter.prototype.reset_searches = function() {
  app.findTextPreferences = NothingEnum.nothing;
  app.changeTextPreferences = NothingEnum.nothing;
  app.findGrepPreferences = NothingEnum.nothing;
  app.changeGrepPreferences = NothingEnum.nothing;
}

Reimporter.prototype.change_text = function(findWhat, changeTo) {
  app.findTextPreferences.findWhat = findWhat;
  app.changeTextPreferences.changeTo = changeTo;
  this.doc.changeText();
}

Reimporter.prototype.change_grep = function(findWhat, changeTo) {
  app.findGrepPreferences.findWhat = findWhat;
  app.changeGrepPreferences.changeTo = changeTo;
  this.doc.changeGrep();
}

Reimporter.prototype.post_fix_masters = function() {
  if (!this.ui_post_fix_masters.checkedState)
    return;

  // title page is B-Master
  var title_page = this.doc.pages[0];
  title_page.appliedMaster = this.b_master;

  for (var i = 1; i < this.doc.pages.length; ++ i) {
    var page = this.doc.pages[i];
    if (this.page_is_empty(page) || this.page_is_chapter(page)) {
      page.appliedMaster = this.b_master;
    } else {
      page.appliedMaster = this.a_master;
    }
  }
}

Reimporter.prototype.post_update_toc = function() {
  if (!this.have_toc)
    return;

  if (!this.ui_post_update_toc.checkedState)
    return;

  var style_index = this.ui_post_toc_style.selectedIndex;
  var style_name = this.toc_styles[style_index];
  var style = this.doc.tocStyles.itemByName(style_name);
  this.doc.createTOC(style, true);
}

Reimporter.prototype.page_is_empty = function(page) {
  if (page.pageItems.length == 0) {
    return true;
  }
  if (this.main_frame(page).contents == "") {
    return true;
  }
}

Reimporter.prototype.page_is_chapter = function(page) {
  var frame = this.main_frame(page);
  var paragraph = frame.paragraphs[0];
  if (paragraph.startParagraph == StartParagraph.NEXT_PAGE ||
    paragraph.startParagraph == StartParagraph.NEXT_ODD_PAGE) {
    return true;
  }
  if (paragraph.appliedParagraphStyle.name.toLowerCase().indexOf("title") != -1) {
    return true;
  }
  return false;
}

Reimporter.prototype.disable_grep = function() {
  if (!this.ui_disable_grep.checkedState)
    return;

  pstyles = this.doc.allParagraphStyles;
  for (var i = 0; i < pstyles.length; ++ i) {
    pstyle = pstyles[i];
    gstyles = pstyle.nestedGrepStyles;
    for (var j = 0; j < gstyles.length; ++ j) {
      gstyle = gstyles[j];
      if (gstyle.grepExpression[0] != '*')
        gstyle.grepExpression = '*' + gstyle.grepExpression;
    }
  }
}

Reimporter.prototype.enable_grep = function() {
  if (!this.ui_disable_grep.checkedState)
    return;

  pstyles = this.doc.allParagraphStyles;
  for (var i = 0; i < pstyles.length; ++ i) {
    pstyle = pstyles[i];
    gstyles = pstyle.nestedGrepStyles;
    for (var j = 0; j < gstyles.length; ++ j) {
      gstyle = gstyles[j];
      if (gstyle.grepExpression[0] == '*')
        gstyle.grepExpression = gstyle.grepExpression.substr(1);
    }
  }
}

Reimporter.prototype.disable_reflow = function() {
  if (!this.ui_disable_reflow.checkedState)
    return;

  if (this.reflow_changed)
    return;

  this.saved_reflow = this.doc.textPreferences.smartTextReflow;
  this.doc.textPreferences.smartTextReflow = false;
  this.reflow_changed = true;
}

Reimporter.prototype.restore_reflow = function() {
  if (!this.ui_disable_reflow.checkedState)
    return;

  if (!this.reflow_changed)
    return;

  var saved_preflight = this.doc.preflightOptions.preflightOff;

  this.doc.preflightOptions.preflightOff = false; 
  this.doc.textPreferences.smartTextReflow = this.saved_reflow;
  this.doc.activeProcess.waitForProcess(30);
  this.doc.preflightOptions.preflightOff = saved_preflight;

  this.reflow_changed = false;
}

Reimporter.prototype.main_frame = function(page) {
  var frames = page.textFrames;
  for (var i = 0; i < frames.length; ++ i) {
    try {
      var frame = frames[i];
      var master = frame.overriddenMasterPageItem;
      if (master.nextTextFrame != null || master.previousTextFrame != null) {
        return frame;
      }
    } catch (e) {
    }
  }
  return frames[0];
}

var reimporter = new Reimporter();
reimporter.run();
