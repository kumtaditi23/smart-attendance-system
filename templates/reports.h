{% extends "base.html" %}
{% block title %}Reports — FaceAttend{% endblock %}
{% block content %}
<div class="page-header">
  <div>
    <div class="page-title">Reports</div>
    <div class="page-subtitle">Filter by subject and date</div>
  </div>
</div>

<div class="filter-bar">
  <label>Subject</label>
  <select id="subj-filter" onchange="applyFilter()" style="width:auto">
    <option value="">All Subjects</option>
    {% for s in subjects %}
    <option value="{{ s.subject_code }}"
      {% if s.subject_code == selected_subject %}selected{% endif %}>
      {{ s.subject_code }} — {{ s.subject_name }}
    </option>
    {% endfor %}
  </select>
  <label>Date</label>
  <input type="date" id="date-filter" value="{{ selected_date }}"
         style="width:auto" onchange="applyFilter()">
  <span class="badge badge-gray">{{ records|length }} record(s)</span>
  <div class="export-btn">
    <a href="/api/export/csv?date={{ selected_date }}&subject={{ selected_subject }}"
       class="btn btn-success">&#8681; Export CSV</a>
  </div>
</div>

<div class="reports-grid">
  <div class="card">
    <div class="card-title">Attendance Records</div>
    {% if records %}
    <div class="table-wrap">
    <table>
      <thead><tr><th>Name</th><th>ID</th><th>Subject</th><th>Teacher</th><th>Time</th></tr></thead>
      <tbody>
        {% for r in records %}
        <tr>
          <td><strong>{{ r.name }}</strong></td>
          <td><span class="badge badge-blue">{{ r.student_id }}</span></td>
          <td><span class="badge badge-purple">{{ r.subject_code }}</span> {{ r.subject_name }}</td>
          <td style="color:var(--text-muted)">{{ r.teacher_name }}</td>
          <td style="color:var(--text-muted)">{{ r.time }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
    {% else %}
    <div class="empty-state"><p>No records for this filter.</p></div>
    {% endif %}
  </div>

  <div class="card">
    <div class="card-title">Student Summary</div>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Student</th><th>Classes Attended</th></tr></thead>
      <tbody>
        {% for r in summary %}
        <tr>
          <td>
            <a href="/student/{{ r.student_id }}" style="color:var(--dark3);font-weight:500;text-decoration:none">
              {{ r.name }}
            </a>
          </td>
          <td><span class="badge badge-green">{{ r.classes_attended }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
function applyFilter() {
  const s = document.getElementById('subj-filter').value;
  const d = document.getElementById('date-filter').value;
  window.location.href = `/reports?date=${d}&subject=${s}`;
}
</script>
{% endblock %}