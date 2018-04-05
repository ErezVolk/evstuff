// ex: set et sw=2:

// TODO: Find the rerunner script!
// TODO: Multiple main stories are a no-no
// TODO: Split (and unsplit!) frames on specific styles
// TODO: Configurable (and savable) Title matcher (r'Title|Frame Top')
// TODO: Maybe do the start of line trick?
// TODO: Remove unused imported styles
// TODO: Status notification
// TODO: Change "old load" checkbox to radio
// TODO: Save settings in a variable
// TODO: Offer the precooked searches!
// TODO: Proper master page fixer
// TODO: Index stuff
// TODO: Clear (or do a story break) after "EREZ EREZ"

function ri_main() {
  ri = {
    doc: app.activeDocument,
    reflow_changed: false,
    messages: []
  };
  ri_run(ri);
}

function ri_run(ri) {
  ri_analyze(ri);

  if (!ri_get_options(ri))
    return;

  if (ri.uig_import.checkedState)
    if (!ri_get_importee(ri))
      return;

  ri_start_counter(ri);
  ri_disable_grep(ri);
  ri_disable_reflow(ri);
  if (ri.uig_pre.checkedState) {
    ri_pre_remaster(ri);
    ri_pre_clear(ri);
  }
  if (ri.uig_import.checkedState) {
    ri_do_import(ri);
  }
  if (ri.uig_post.checkedState) {
    ri_post_clear_overrides(ri);
    ri_reset_searches(ri);
    ri_post_fix_spaces(ri);
    ri_post_fix_dashes(ri);
    ri_post_remove_footnote_whitespace(ri);
  }
  if (ri.uig_groom.checkedState) {
    ri_groom_fully_justify(ri);
    ri_restore_reflow(ri);
    ri_groom_fix_masters(ri);
    ri_groom_update_toc(ri);
  }
  ri_enable_grep(ri);
  ri_restore_reflow(ri);
  ri_stop_counter(ri);
};

function ri_start_counter(ri) {
  ri.start_ms = new Date().valueOf();
}

function ri_stop_counter(ri) {
  end_ms = new Date().valueOf();
  elapsed = (end_ms - ri.start_ms) / 1000.0;

  ri.messages.unshift("Done in " + String(elapsed) + " Sec.");
  alert(ri.messages.join('\n'));
}

function ri_analyze(ri) {
  var vars = ri.doc.textVariables;
  ri.var_saved = null;
  ri.str_saved = null;

  for (var i = 0; i < vars.length; ++ i) {
    var cur = vars[i]
    if (cur.variableType == VariableTypes.CUSTOM_TEXT_TYPE && cur.name == "Imported From") {
      ri.var_saved = cur;
      ri.str_saved = cur.variableOptions.contents;
      break;
    }
  }

  var stories = ri.doc.stories;
  ri.have_toc = false;
  if (ri.doc.tocStyles.length > 1) {
    ri.toc_styles = ri.doc.tocStyles.everyItem().name;
    ri.toc_styles.shift();
    for (var i = 0; i < stories.length && !ri.have_toc; ++ i) {
      ri.have_toc = (stories[i].storyType == StoryTypes.TOC_STORY);
    }
  }
}

function ri_get_options(ri) {
  var dlg = app.dialogs.add({name: "ReImport Options"});
  with (dlg) {
    with (dialogColumns.add()) {
      with (ri.uig_pre = enablingGroups.add({staticLabel: "Pre-Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          ri.ui_pre_remaster =
            checkboxControls.add({
              staticLabel: "Reset all master pages",
              checkedState: true
            });
          ri.ui_pre_clear =
            checkboxControls.add({
              staticLabel: "Remove all text",
              checkedState: true
            });
        }
      }

      with (ri.uig_import = enablingGroups.add({staticLabel: "Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          if (ri.str_saved) {
            ri.ui_same_importee = checkboxControls.add({
              staticLabel: "Reload " + String(ri.str_saved),
              checkedState: true
            });
          }
          ri.ui_import_options = checkboxControls.add({
            staticLabel: "Show import options",
            checkedState: true
          });
        }
      }

      with (ri.uig_post = enablingGroups.add({staticLabel: "Post-Import", checkedState: true})) {
        with (dialogColumns.add() ) {
          ri.ui_post_clear_overrides =
            checkboxControls.add({
              staticLabel: "Clear all imported style overrides",
              checkedState: true
            });
          ri.ui_post_fix_spaces =
            checkboxControls.add({
              staticLabel: "Eliminate multiple spaces",
              checkedState: true
            });
          ri.ui_post_fix_dashes =
            checkboxControls.add({
              staticLabel: "Fix spacing around dashes",
              checkedState: true
            });
          ri.ui_post_remove_footnote_whitespace =
            checkboxControls.add({
              staticLabel: "Remove leading whitespace in footnotes",
              checkedState: true
            });
        }
      }

      with (ri.uig_groom = enablingGroups.add({staticLabel: "Grooming", checkedState: true})) {
        with (dialogColumns.add() ) {
          ri.ui_groom_fully_justify =
            checkboxControls.add({
              staticLabel: "Fix to full justification",
              checkedState: true
            });
          ri.ui_groom_fix_masters =
            checkboxControls.add({
              staticLabel: "Fix master pages",
              checkedState: true
            });
          if (ri.have_toc) {
            ri.ui_groom_update_toc =
              checkboxControls.add({
                staticLabel: "Update TOC",
                checkedState: true
              });
            ri.ui_groom_toc_style = dropdowns.add({
              stringList: ri.toc_styles,
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
          var masters = ri.doc.masterSpreads.everyItem().name;
          ri.ui_a_master = dropdowns.add({stringList: masters, selectedIndex: 0});
          ri.ui_b_master = dropdowns.add({stringList: masters, selectedIndex: masters.length - 1});
        }
      }

      with (checkboxControls) {
        with (dialogColumns.add()) {
          ri.ui_disable_grep = add({
            staticLabel: "Disable GREP styles while working",
            checkedState: true
          });
          ri.ui_disable_reflow = add({
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

  ri.a_master = ri.doc.masterSpreads.itemByName(masters[ri.ui_a_master.selectedIndex]);
  ri.b_master = ri.doc.masterSpreads.itemByName(masters[ri.ui_b_master.selectedIndex]);
  return true;
}

function ri_get_importee(ri) {
  if (ri.str_saved && ri.ui_same_importee.checkedState)
    ri.importee = ri.str_saved;
  else
    ri.importee = File.openDialog("Choose your importee", ri.filter_files)
  return ri.importee;
};

function ri_filter_files(ri, file) {
  if (file.constructor.name == "Folder") {
    return true;
  }
  if (file.name.match(/\.(docx?|txt|idtt)$/)) {
    return true;
  }
  return false;
};

function ri_pre_remaster(ri) {
  if (!ri.ui_pre_remaster.checkedState)
    return;
  ri.doc.pages.everyItem().appliedMaster = ri.a_master;
};

function ri_pre_clear(ri) {
  if (!ri.ui_pre_clear.checkedState)
    return;
  var page = ri.doc.pages[0];
  ri_main_frame(ri, page).parentStory.contents = "";
  //ri_override_all_master_page_items(ri, page);
};

function ri_override_all_master_page_items(ri, page) {
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

function ri_do_import(ri) {
  var page = ri.doc.pages[0];
  var frame = ri_main_frame(ri, page);
  try {
    frame.place(ri.importee, ri.ui_import_options.checkedState);
  } catch (e) {
    alert("Note: Import failed(?)\n" + e);
  }
  if (!ri.var_saved)
    ri.var_saved = ri.doc.textVariables.add({
      name: "Imported From",
      variableType: VariableTypes.CUSTOM_TEXT_TYPE
    });
  ri.var_saved.variableOptions.contents = ri.importee;
};

function ri_post_clear_overrides(ri) {
  if (!ri.ui_post_clear_overrides.checkedState)
    return;
  ri.doc.stories.everyItem().clearOverrides();
  try {
    ri.doc.stories.everyItem().footnotes.everyItem().texts.everyItem().clearOverrides();
  }
  catch (e) {
  }
};

function ri_post_fix_spaces(ri) {
  if (!ri.ui_post_fix_spaces.checkedState)
    return;

  // Multiple Space to Single Space
  ri_change_grep(ri, "[~m~>~f~|~S~s~<~/~.~3~4~% ]{2,}", "\\s");

  // No whitespace at the end of paragraphs (doesn't work!?)
  ri_change_grep(ri, "\\s+$", "");
};

function ri_post_fix_dashes(ri) {
  if (!ri.ui_post_fix_dashes.checkedState)
    return;

  ri_change_grep(ri, "[ ~<]+~=[ ~k~<]+", "~<~=~k~<");
};

function ri_post_remove_footnote_whitespace(ri) {
  if (!ri.ui_post_remove_footnote_whitespace.checkedState)
    return;

  app.findGrepPreferences.findWhat = "(?<=^~F\\t) +";
  app.changeGrepPreferences.changeTo = "";
  try {
    ri.doc.stories.everyItem().footnotes.everyItem().texts.everyItem()
      .changeGrep();
  }
  catch (e) {
  }
};

function ri_groom_fully_justify(ri) {
  if (!ri.ui_groom_fully_justify.checkedState)
    return;

  var page = ri.doc.pages[0];
  var frame = page.textFrames[0];
  var story = frame.parentStory;
  var paragraphs = story.paragraphs;

  var prefs = ri.doc.viewPreferences;
  var oldUnits = prefs.horizontalMeasurementUnits;
  prefs.horizontalMeasurementUnits = MeasurementUnits.pixels;

  var changed = 0;
  for (var i = 0; i < paragraphs.count(); ++ i)
    if (ri_fully_justify(ri, paragraphs[i]))
      ++ changed;

  prefs.horizontalMeasurementUnits = oldUnits;

  if (changed) {
    ri.messages.push(
      'Justification changed for ' +
      String(changed) +
      ' of ' +
      String(paragraphs.count()) +
      ' paragraph(s)'
    );
  }
};

function ri_fully_justify(ri, paragraph) {
  if (paragraph.paragraphDirection != ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION) {
    // We only know about RTL
    return false;
  }

  var justification = paragraph.justification;
  if (justification == Justification.FULLY_JUSTIFIED) {
    // Currently fully justified, may be intentional
    var style = paragraph.appliedParagraphStyle;
    if (style && style.justification == Justification.FULLY_JUSTIFIED) {
      // If that's what the user likes...
      return false;
    }
  } else if (justification != Justification.RIGHT_JUSTIFIED) {
    // Some kind of fancy centered paragraph.
    return false;
  }


  var lines = paragraph.lines;
  var numLines = lines.count()
  var lastLine = lines[-1];
  var lastLineFrame = lastLine.parentTextFrames[0];
  if (lastLineFrame == undefined) {
    return false;
  }

  var lastChar = lastLine.characters[-1];
  if (lastChar == '\n') {
    lastChar = lastLine.characters[-2];
  }

  var fully = null;
  var right = null;

  if (lines.count() > 1) {
    ri.last_good_line = lines[-2];
    ri.last_good_line = ri.last_good_line.characters[-1];
  }

  if (justification == Justification.FULLY_JUSTIFIED) {
    // Currently fully justified, we know the margin
    fully = lastChar.endHorizontalOffset;
    paragraph.justification = Justification.RIGHT_JUSTIFIED;
    right = lastChar.endHorizontalOffset;
  } else if (ri.last_good_line != undefined) {
    // We have something to compare with!
    right = lastChar.endHorizontalOffset;
    fully = ri.last_good_char.endHorizontalOffset;

    var last_good_frame = ri.last_good_line.parentTextFrames[0];

    if (last_good_frame != lastLineFrame) {
      fully -= last_good_frame.parentPage.bounds[1];
      fully += lastLineFrame.parentPage.bounds[1];
    }
  } else {
    // Change and compare
    right = lastChar.endHorizontalOffset;
    right = lastChar.endHorizontalOffset;
    paragraph.justification = Justification.FULLY_JUSTIFIED;
    fully = lastChar.endHorizontalOffset;
  }

  var gap = right - fully;
  var fudge = lastChar.pointSize / 2;

  if (gap != 0 && gap < fudge && gap > -fudge) {
    paragraph.justification = Justification.FULLY_JUSTIFIED;
    ri.last_good_line = lastLine;
    ri.last_good_char = lastChar;
  } else {
    paragraph.justification = Justification.RIGHT_JUSTIFIED;
  }

  return (paragraph.justification != justification);
}

function ri_reset_searches(ri) {
  app.findTextPreferences = NothingEnum.nothing;
  app.changeTextPreferences = NothingEnum.nothing;
  app.findGrepPreferences = NothingEnum.nothing;
  app.changeGrepPreferences = NothingEnum.nothing;
}

function ri_change_text(ri, findWhat, changeTo) {
  app.findTextPreferences.findWhat = findWhat;
  app.changeTextPreferences.changeTo = changeTo;
  ri.doc.changeText();
}

function ri_change_grep(ri, findWhat, changeTo) {
  app.findGrepPreferences.findWhat = findWhat;
  app.changeGrepPreferences.changeTo = changeTo;
  ri.doc.changeGrep();
}

function ri_groom_fix_masters(ri) {
  if (!ri.ui_groom_fix_masters.checkedState)
    return;

  // title page is B-Master
  var title_page = ri.doc.pages[0];
  title_page.appliedMaster = ri.b_master;

  for (var i = 1; i < ri.doc.pages.length; ++ i) {
    var page = ri.doc.pages[i];
    if (ri_page_is_empty(ri, page) || ri_page_is_chapter(ri, page)) {
      page.appliedMaster = ri.b_master;
    } else {
      page.appliedMaster = ri.a_master;
    }
  }
}

function ri_groom_update_toc(ri) {
  if (!ri.have_toc)
    return;

  if (!ri.ui_groom_update_toc.checkedState)
    return;

  var style_index = ri.ui_groom_toc_style.selectedIndex;
  var style_name = ri.toc_styles[style_index];
  var style = ri.doc.tocStyles.itemByName(style_name);
  ri.doc.createTOC(style, true);
}

function ri_page_is_empty(ri, page) {
  if (page.pageItems.length == 0) {
    return true;
  }
  if (ri_main_frame(ri, page).contents == "") {
    return true;
  }
}

function ri_page_is_chapter(ri, page) {
  var frame = ri_main_frame(ri, page);
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

function ri_disable_grep(ri) {
  if (!ri.ui_disable_grep.checkedState)
    return;

  pstyles = ri.doc.allParagraphStyles;
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

function ri_enable_grep(ri) {
  if (!ri.ui_disable_grep.checkedState)
    return;

  pstyles = ri.doc.allParagraphStyles;
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

function ri_disable_reflow(ri) {
  if (!ri.ui_disable_reflow.checkedState)
    return;

  if (ri.reflow_changed)
    return;

  ri.saved_reflow = ri.doc.textPreferences.smartTextReflow;
  ri.doc.textPreferences.smartTextReflow = false;
  ri.reflow_changed = true;
}

function ri_restore_reflow(ri) {
  if (!ri.ui_disable_reflow.checkedState)
    return;

  if (!ri.reflow_changed)
    return;

  var saved_preflight = ri.doc.preflightOptions.preflightOff;

  ri.doc.preflightOptions.preflightOff = false; 
  ri.doc.textPreferences.smartTextReflow = ri.saved_reflow;
  ri.doc.activeProcess.waitForProcess(30);
  ri.doc.preflightOptions.preflightOff = saved_preflight;

  ri.reflow_changed = false;
}

function ri_main_frame(ri, page) {
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

ri_main();
