import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Clean up known mangled lines from previous failures
# Line 873 area mangling: fetchData();pi/system/import-start`, {
import re
content = re.sub(r'fetchData\(\);pi/system/import-start\`, \{[^;]+;', 'fetchData();', content)

# 2. Add isRestarting state
if 'const [isRestarting, setIsRestarting] = useState(false);' not in content:
    content = content.replace('const [isSaving, setIsSaving] = useState(false);', 
                              'const [isSaving, setIsSaving] = useState(false);\n  const [isRestarting, setIsRestarting] = useState(false);')

# 3. Update handleRestartBackend for better UX
new_handler = """  const handleRestartBackend = async () => {
    if (!window.confirm("Restart backend service? This will briefly interrupt the API.")) return;
    setIsRestarting(true);
    try {
      await fetch(`${API_BASE}/api/system/restart`, { method: 'POST' });
      // Keep state for 8 seconds to allow reload
      setTimeout(() => {
        setIsRestarting(false);
        fetchData();
        alert("Backend restart complete.");
      }, 8000);
    } catch (e) {
      alert("Failed to trigger restart: " + e);
      setIsRestarting(false);
    }
  };"""

# Replace old handler
old_handler_pattern = r'const handleRestartBackend = async \(\) => \{[\s\S]+?\};'
content = re.sub(old_handler_pattern, new_handler, content)

# 4. Update the button rendering
# <button className="btn btn-scan" style={{ backgroundColor: '#dc2626', marginLeft: '10px', color: 'white' }} onClick={handleRestartBackend}>⚠️ Restart Backend</button>
new_button = """<button 
            className="btn btn-scan" 
            style={{ 
              backgroundColor: isRestarting ? '#94a3b8' : '#dc2626', 
              marginLeft: '10px', 
              color: 'white',
              cursor: isRestarting ? 'not-allowed' : 'pointer',
              opacity: isRestarting ? 0.7 : 1
            }} 
            onClick={handleRestartBackend}
            disabled={isRestarting}
          >
            {isRestarting ? '⏳ RESTARTING...' : '⚠️ RESTART BACKEND'}
          </button>"""

content = content.replace('<button className="btn btn-scan" style={{ backgroundColor: \'\#dc2626\', marginLeft: \'10px\', color: \'white\' }} onClick={handleRestartBackend}>⚠️ Restart Backend</button>', new_button)

# Also fix the fetchData area just in case
content = content.replace('fetchData();pi/system/import-start`, {rt-status`;', 'fetchData();')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Frontend UX improved and mangled lines cleaned")
