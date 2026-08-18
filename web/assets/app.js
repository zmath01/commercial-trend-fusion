/* commercial-trend — client-side interactivity (filters + force graph) */
(function () {
  "use strict";

  /* ---- field filter on concepts table ---- */
  var filterBtns = document.querySelectorAll(".filters button[data-field]");
  var conceptRows = document.querySelectorAll("tr[data-field]");
  filterBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var f = btn.getAttribute("data-field");
      filterBtns.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      conceptRows.forEach(function (row) {
        var show = f === "All" || row.getAttribute("data-field") === f;
        row.classList.toggle("hidden", !show);
      });
    });
  });

  /* ---- force-directed fusion graph ---- */
  var graphEl = document.getElementById("graph");
  var graphData = window.FUSION_GRAPH || null;
  if (graphEl && graphData) {
    if (typeof d3 === "undefined") {
      graphEl.innerHTML = '<div class="fallback">d3.js failed to load from CDN — ' +
        'the fusion table below still works.</div>';
    } else {
      try {
        var width = graphEl.clientWidth, height = graphEl.clientHeight;
        var svg = d3.select(graphEl).append("svg")
          .attr("width", width).attr("height", height);
        var sim = d3.forceSimulation(graphData.nodes)
          .force("link", d3.forceLink(graphData.links).id(function (d) { return d.id; })
            .distance(48).strength(0.4))
          .force("charge", d3.forceManyBody().strength(-160))
          .force("center", d3.forceCenter(width / 2, height / 2))
          .force("collide", d3.forceCollide(14));

        var link = svg.append("g")
          .selectAll("line").data(graphData.links).join("line")
          .attr("stroke", function (d) { return d.type === "predicted" ? "#d29922" : "#30363d"; })
          .attr("stroke-width", function (d) { return d.type === "predicted" ? 1.6 : 1; })
          .attr("stroke-dasharray", function (d) { return d.type === "predicted" ? "4 3" : null; });

        var node = svg.append("g")
          .selectAll("circle").data(graphData.nodes).join("circle")
          .attr("r", function (d) { return Math.min(9, 4 + Math.sqrt(d.freq || 10) / 3); })
          .attr("fill", function (d) { return d.color || "#58a6ff"; })
          .attr("stroke", "#0d1117").attr("stroke-width", 1.2)
          .call(d3.drag()
            .on("start", dragstarted).on("drag", dragged).on("end", dragended));

        node.append("title").text(function (d) { return d.id; });

        var label = svg.append("g").selectAll("text").data(graphData.nodes).join("text")
          .attr("x", 12).attr("y", 4).attr("font-size", 11).attr("fill", "#8b949e")
          .text(function (d) { return d.id; });

        sim.on("tick", function () {
          link.attr("x1", function (d) { return d.source.x; })
              .attr("y1", function (d) { return d.source.y; })
              .attr("x2", function (d) { return d.target.x; })
              .attr("y2", function (d) { return d.target.y; });
          node.attr("cx", function (d) { return d.x; }).attr("cy", function (d) { return d.y; });
          label.attr("x", function (d) { return d.x + 12; })
               .attr("y", function (d) { return d.y + 4; });
        });

        function dragstarted(event, d) { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
        function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
        function dragended(event, d) { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }
      } catch (e) {
        graphEl.innerHTML = '<div class="fallback">graph render failed: ' + e.message + "</div>";
      }
    }
  }
})();
