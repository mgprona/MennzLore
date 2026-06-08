// State Variables
let currentProject = 'time-machine-project';
let episodes = [];
let currentEpisodeIndex = 0;
let isPlaying = false;
let playInterval = null;
let projectData = {};

// DOM Elements
const projectSelect = document.getElementById('project-select');
const episodeList = document.getElementById('episode-list');
const mapContainer = document.getElementById('map-container');
const slider = document.getElementById('timeline-slider');
const timelineVal = document.getElementById('timeline-val');
const timelineLabels = document.getElementById('timeline-labels');
const btnPlay = document.getElementById('btn-play');
const playIcon = document.getElementById('play-icon');
const detailsContent = document.getElementById('details-content');
const tooltip = document.getElementById('tooltip');

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadProject(currentProject);
    
    projectSelect.addEventListener('change', (e) => {
        currentProject = e.target.value;
        loadProject(currentProject);
    });

    btnPlay.addEventListener('click', togglePlay);
    slider.addEventListener('input', handleSliderInput);
});

// Load a Project's Data
function loadProject(project) {
    // Reset play state
    stopPlay();
    
    // Fetch project manifest / pipeline state from server
    fetch(`/api/project/${project}`)
        .then(res => res.json())
        .then(data => {
            projectData = data;
            episodes = data.episodes || [];
            setupTimeline();
            setupEpisodeList();
            loadMapAndDetails(0); // Load first episode
        })
        .catch(err => {
            console.error('Failed to load project details:', err);
            // Fallback mock data if server is offline or empty
            mockProjectData();
        });
}

function setupTimeline() {
    slider.min = 1;
    slider.max = episodes.length;
    slider.value = 1;
    currentEpisodeIndex = 0;
    timelineVal.textContent = episodes[0] ? episodes[0].id : 'EP001';
    
    // Labels
    timelineLabels.innerHTML = '';
    episodes.forEach((ep, idx) => {
        const span = document.createElement('span');
        span.textContent = ep.id;
        span.style.cursor = 'pointer';
        span.addEventListener('click', () => {
            slider.value = idx + 1;
            selectEpisode(idx);
        });
        timelineLabels.appendChild(span);
    });
}

function setupEpisodeList() {
    episodeList.innerHTML = '';
    episodes.forEach((ep, idx) => {
        const li = document.createElement('li');
        li.className = 'episode-item' + (idx === 0 ? ' active' : '');
        li.innerHTML = `
            <div>
                <div class="episode-title">${ep.title}</div>
                <div class="episode-meta">${ep.id} | ${ep.scenes_count} Scenes | ${ep.events_count} Events</div>
            </div>
            <span class="material-icons-round" style="font-size: 18px; color: var(--accent-color);">chevron_right</span>
        `;
        li.addEventListener('click', () => {
            slider.value = idx + 1;
            selectEpisode(idx);
        });
        episodeList.appendChild(li);
    });
}

function handleSliderInput(e) {
    const idx = parseInt(e.target.value) - 1;
    selectEpisode(idx);
}

function selectEpisode(idx) {
    if (idx < 0 || idx >= episodes.length) return;
    
    currentEpisodeIndex = idx;
    timelineVal.textContent = episodes[idx].id;
    
    // Update active list item
    const items = episodeList.querySelectorAll('.episode-item');
    items.forEach((item, itemIdx) => {
        if (itemIdx === idx) {
            item.classList.add('active');
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            item.classList.remove('active');
        }
    });
    
    loadMapAndDetails(idx);
}

function togglePlay() {
    if (isPlaying) {
        stopPlay();
    } else {
        startPlay();
    }
}

function startPlay() {
    isPlaying = true;
    playIcon.textContent = 'pause';
    
    playInterval = setInterval(() => {
        let nextIdx = currentEpisodeIndex + 1;
        if (nextIdx >= episodes.length) {
            nextIdx = 0;
        }
        slider.value = nextIdx + 1;
        selectEpisode(nextIdx);
    }, 3500); // Change episode every 3.5 seconds
}

function stopPlay() {
    isPlaying = false;
    playIcon.textContent = 'play_arrow';
    if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
    }
}

// Fetch and Render Map SVG & Episode Details
function loadMapAndDetails(idx) {
    const ep = episodes[idx];
    if (!ep) return;
    
    // Load SVG Map
    fetch(`/api/project/${currentProject}/map`)
        .then(res => res.text())
        .then(svgText => {
            mapContainer.innerHTML = svgText;
            animateMapForEpisode(ep.id);
        })
        .catch(err => {
            console.error('Failed to load SVG map:', err);
        });
        
    // Fetch detailed micro-facts for this chapter to render details & D3 graph
    fetch(`/api/project/${currentProject}/episode/${ep.id}`)
        .then(res => res.json())
        .then(epData => {
            renderDetails(epData);
            renderSocialGraph(epData);
        })
        .catch(err => {
            console.error('Failed to load episode details:', err);
        });
}

// Animate / Filter elements inside the Map SVG based on the selected episode
function animateMapForEpisode(episodeId) {
    const svgEl = mapContainer.querySelector('svg');
    if (!svgEl) return;
    
    // Parse episodes mentioned in locations/routes from the metadata
    const locations = svgEl.querySelectorAll('#locations g');
    const routes = svgEl.querySelectorAll('#routes g');
    
    // Fade out everything not mentioned in this episode, highlight matching ones
    locations.forEach(loc => {
        const name = loc.getAttribute('data-name');
        const matches = checkLocationInEpisode(name, episodeId);
        
        if (matches) {
            loc.style.opacity = '1';
            const circle = loc.querySelector('circle');
            if (circle) {
                circle.setAttribute('r', '8');
                circle.style.fill = '#3b82f6';
                circle.style.stroke = '#ffffff';
                circle.style.strokeWidth = '2';
            }
        } else {
            loc.style.opacity = '0.25';
            const circle = loc.querySelector('circle');
            if (circle) {
                circle.setAttribute('r', '4');
                circle.style.fill = '#5a4a3a';
                circle.style.stroke = 'none';
            }
        }
        
        // Hover details
        loc.style.cursor = 'pointer';
        loc.addEventListener('mouseover', (e) => {
            showTooltip(e, `<strong>${name}</strong><br>Terrain: ${loc.getAttribute('data-terrain')}`);
        });
        loc.addEventListener('mouseout', hideTooltip);
    });
    
    routes.forEach(route => {
        const from = route.getAttribute('data-from');
        const to = route.getAttribute('data-to');
        
        // Simple logic: route is active if both locations are active
        const active = checkLocationInEpisode(from, episodeId) && checkLocationInEpisode(to, episodeId);
        if (active) {
            route.style.opacity = '1';
            const line = route.querySelector('line');
            if (line) {
                line.style.stroke = '#ef4444';
                line.style.strokeWidth = '2.5';
            }
        } else {
            route.style.opacity = '0.08';
            const line = route.querySelector('line');
            if (line) {
                line.style.stroke = '#8b3a3a';
                line.style.strokeWidth = '1.5';
            }
        }
    });
}

function checkLocationInEpisode(locationName, episodeId) {
    if (!projectData.locations_map) return true; // fallback
    const locMeta = projectData.locations_map[locationName.toLowerCase().trim()];
    if (locMeta && locMeta.episodes) {
        return locMeta.episodes.includes(episodeId);
    }
    return false;
}

// Render HTML Details panel
function renderDetails(epData) {
    let html = `
        <div class="detail-card">
            <h4>${epData.chapter_title || 'Episode Details'}</h4>
            <p><strong>Chapter ID:</strong> ${epData.chapter_id}</p>
            <p style="margin-top: 8px;"><strong>Total Events:</strong> ${epData.total_events_count} | <strong>Scenes:</strong> ${epData.total_scenes_count}</p>
        </div>
        
        <div class="section-title">
            <span class="material-icons-round">view_timeline</span>
            Key Plot Points
        </div>
    `;
    
    if (epData.key_plot_points && epData.key_plot_points.length > 0) {
        epData.key_plot_points.forEach(kpp => {
            html += `
                <div class="detail-card">
                    <h4>KPP-${kpp.point_id.replace('KPP-', '')} (Scene ${kpp.in_scene_id})</h4>
                    <p>${kpp.description}</p>
                    <p style="font-size: 11px; margin-top: 6px; color: var(--accent-color);">
                        Characters: ${kpp.characters_involved.join(', ')}
                    </p>
                </div>
            `;
        });
    } else {
        html += `<p style="font-size:13px; color:var(--text-secondary);">No plot points defined.</p>`;
    }
    
    html += `
        <div class="section-title" style="margin-top:20px;">
            <span class="material-icons-round">local_offer</span>
            Items of Interest
        </div>
    `;
    
    if (epData.items_of_interest && epData.items_of_interest.length > 0) {
        epData.items_of_interest.forEach(item => {
            html += `
                <div class="detail-card">
                    <h4>${item.item}</h4>
                    <p>${item.description}</p>
                    <p style="font-style:italic; font-size:12px; margin-top:4px; color:var(--text-secondary);">Role: ${item.role_in_chapter}</p>
                </div>
            `;
        });
    } else {
        html += `<p style="font-size:13px; color:var(--text-secondary); margin-bottom: 20px;">No items found.</p>`;
    }
    
    detailsContent.innerHTML = html;
}

// Render D3.js Social Graph of character interactions
function renderSocialGraph(epData) {
    const svg = d3.select("#social-graph");
    svg.selectAll("*").remove(); // clear canvas
    
    const width = svg.node().getBoundingClientRect().width || 340;
    const height = svg.node().getBoundingClientRect().height || 280;
    
    // Assemble Nodes and Links
    const characters = epData.characters_present || [];
    if (characters.length === 0) {
        svg.append("text")
            .attr("x", width/2)
            .attr("y", height/2)
            .attr("text-anchor", "middle")
            .style("fill", "var(--text-secondary)")
            .text("No character relationship data");
        return;
    }
    
    const nodes = characters.map(name => ({ id: name }));
    const links = [];
    
    // Build links from dialogs or connections
    if (epData.dialogue_summaries) {
        epData.dialogue_summaries.forEach(dlg => {
            const p = dlg.participants;
            if (p && p.length >= 2) {
                // Connect all participants
                for (let i = 0; i < p.length; i++) {
                    for (let j = i + 1; j < p.length; j++) {
                        links.push({
                            source: p[i],
                            target: p[j],
                            value: 2,
                            type: 'dialogue'
                        });
                    }
                }
            }
        });
    }
    
    if (epData.cross_chapter_connections) {
        epData.cross_chapter_connections.forEach(conn => {
            links.push({
                source: conn.from_entity,
                target: conn.to_entity,
                value: 4,
                type: conn.connection_type || 'relationship'
            });
        });
    }
    
    // Filter nodes that are actually connected or present
    const nodeIds = new Set(nodes.map(n => n.id));
    const validLinks = links.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));
    
    // D3 Force Simulation
    const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(validLinks).id(d => d.id).distance(70))
        .force("charge", d3.forceManyBody().strength(-120))
        .force("center", d3.forceCenter(width / 2, height / 2));
        
    // Draw links
    const link = svg.append("g")
        .attr("stroke-opacity", 0.6)
        .selectAll("line")
        .data(validLinks)
        .join("line")
        .attr("stroke", d => {
            if (d.type === 'enemy') return '#ef4444';
            if (d.type === 'alliance') return '#10b981';
            return 'rgba(255,255,255,0.2)';
        })
        .attr("stroke-width", d => d.value);
        
    // Draw nodes
    const node = svg.append("g")
        .selectAll("g")
        .data(nodes)
        .join("g")
        .call(drag(simulation));
        
    node.append("circle")
        .attr("r", 8)
        .attr("fill", "var(--accent-color)")
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.5);
        
    node.append("text")
        .attr("dx", 12)
        .attr("dy", 4)
        .style("font-size", "10px")
        .style("fill", "var(--text-primary)")
        .style("font-weight", "500")
        .text(d => d.id);
        
    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
            
        node
            .attr("transform", d => `translate(${d.x},${d.y})`);
    });
}

// D3 Drag behavior helper
function drag(simulation) {
    function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }
    
    function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
    }
    
    function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }
    
    return d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended);
}

// Tooltip helpers
function showTooltip(e, content) {
    tooltip.innerHTML = content;
    tooltip.style.opacity = '1';
    tooltip.style.left = (e.pageX + 15) + 'px';
    tooltip.style.top = (e.pageY - 15) + 'px';
}

function hideTooltip() {
    tooltip.style.opacity = '0';
}

// Fallback Mock data loader for local testing/offline runs
function mockProjectData() {
    console.log("Loading mock dashboard data...");
    projectData = {
        episodes: [
            { id: "EP001", title: "Introduction & The Machine", scenes_count: 2, events_count: 3 },
            { id: "EP002", title: "Returns & Time Travelling", scenes_count: 2, events_count: 3 }
        ]
    };
    setupTimeline();
    setupEpisodeList();
}
