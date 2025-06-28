async function loadRoster() {
    const team = document.getElementById("teamSelect").value;
    const container = document.getElementById("rosterContainer");
    const backendURL = window.location.origin;
    container.innerHTML = "Loading...";
  
    try {
      const res = await fetch(`${backendURL}/roster/${team}`);
      const data = await res.json();
  
      const headers = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"];
  
      let html = `<h2>${data.team} Roster</h2><table><thead><tr><th>Player</th>`;
      headers.forEach(attr => html += `<th>${attr}</th>`);
      html += `</tr></thead><tbody>`;
  
      data.players.forEach(p => {
        html += `<tr><td><a href="player.html?id=${p._id}">${p.name}</a></td>`;
        headers.forEach(attr => {
          let value = p.attributes[attr];
  
          if (attr === "NG") {
            value = (value ?? 0).toFixed(2);  // show 2 decimal places
          } else {
            value = Math.round(value ?? 0);   // round all other attributes
          }
  
          html += `<td>${value}</td>`;
        });
        html += `</tr>`;
      });
  
      html += `</tbody></table>`;
      container.innerHTML = html;
  
    } catch (err) {
      console.error(err);
      container.innerHTML = "❌ Failed to load roster.";
    }
  }
  