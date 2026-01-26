// ex: set et sw=2:
// deno-lint-ignore-file ban-unused-ignore no-var no-inner-declarations no-with no-prototype-builtins

MY_NAME_RE = RegExp("^ri:[(].*[)]$");

function ri_main() {
  ri = {
    doc: app.activeDocument,
    reflow_changed: false,
    messages: [],
    warnings: []
  };
  ri_run(ri);
}

function ri_run(ri) {
  if (ri.warnings.length > 0) {
    ri.messages.push("\nWARNINGS:");
    ri.messages = ri.messages.concat(ri.warnings);
  }

  ri.messages.unshift("Done.");

  riss_do_sections(ri);

  alert(ri.messages.join('\n'));
}

function riss_do_sections(ri) {
  var frames = ri_get_all_frames_with_para_styles_containins(ri, "@Section@");

  if (frames.length == 0) {
    return 0;
  }

  var i, count = 0;
  var sections = ri.doc.sections;
  try {
    for (i = sections.length - 1; i > 0; -- i) {
      sections[i].remove();
    }
  } catch(e) {
    ri_logw(ri, "Error deleting old sections: " + e);
  }
  for (i = 0; i < frames.length; ++ i) {
    var page = frames[i].parentPage;
    try {
      sections.add(page);
      count ++;
    } catch(e) {
      ri_logw(ri, "Error adding section on page " + (page.index + 1) + ": " + e);
    }
  }

  if (count > 0) {
    ri_log(ri, "Created " + count + " section(s).");
  }
}

function ri_get_all_frames_with_para_styles_containins(ri, substr) {
  var fids = {};
  var paras = ri_get_all_paras_with_styles_containing(ri, substr);
  var frames = [];
  for (var i = 0; i < paras.length; ++ i) {
    try {
      var frame = paras[i].parentTextFrames[0];
    } catch (_e) {
      continue;
    }
    if (!frame || !frame.isValid)
      continue;
    if (!frame.itemLayer || !frame.itemLayer.isValid)
      continue;
    if (MY_NAME_RE.test(frame.itemLayer.name))
      continue;
    var fid = frame.id;
    if (fids.hasOwnProperty(fid))
      continue;
    fids[fid] = true;
    frames.push(frame);
  }

  frames.sort(function(fx, fy){ x = fx.parentPage.index; y = fy.parentPage.index; return x < y ? -1 : x == y ? 0 : 1 });
  return frames;
}

function ri_get_all_paras_with_styles_containing(ri, substr) {
  var paras = [];

  app.findGrepPreferences = NothingEnum.nothing;
  app.findGrepPreferences.findWhat = "^.";
  var styles = ri_filter_styles(ri.doc.allParagraphStyles, substr);
  for (var j = 0; j < styles.length; ++ j) {
    app.findGrepPreferences.appliedParagraphStyle = styles[j];
    var hits = ri.doc.findGrep();
    for (var k = 0; k < hits.length; ++ k) {
      paras.push(hits[k].paragraphs[0]);
    }
  }

  if (paras.length > 0) {
    paras.sort(function(px, py){ x = px.index; y = py.index; return x < y ? -1 : x == y ? 0 : 1 });
  }
  app.findGrepPreferences = NothingEnum.nothing;

  return paras;
}

function ri_filter_styles(all_styles, substr) {
  var styles = [];
  for (var j = 0; j < all_styles.length; ++ j) {
    var style = all_styles[j];
    if (style.name.indexOf(substr) >= 0)
      styles.push(style)
  }

  return styles;
}

function ri_log(ri, msg) {
  ri.messages.push(msg);
}

function ri_logw(ri, msg) {
  ri.warnings.push(msg);
}


ri_main();
