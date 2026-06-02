from weasyprint import HTML

print("🎨 Compiling session_breakdown.html into a polished PDF portfolio...")

# Compile the file directly tracking your custom embedded responsive layout styles
HTML('learn/session_breakdown.html').write_pdf('learn/session_breakdown.pdf')

print("✅ Success! Your asset is ready at: learn/session_breakdown.pdf")
