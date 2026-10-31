package top.niunaijun.blackboxa.view.main

import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import top.niunaijun.blackbox.BlackBoxCore

class ManageAppsActivity : AppCompatActivity() {
    private val bg = Color.rgb(15, 14, 27)
    private val surface = Color.rgb(31, 29, 50)
    private val accent = Color.rgb(177, 154, 250)
    private val muted = Color.rgb(190, 186, 210)
    private var space = 0
    private lateinit var items: LinearLayout
    private lateinit var search: EditText
    private lateinit var count: TextView

    private fun dp(i: Int) = (i * resources.displayMetrics.density + 0.5f).toInt()
    private fun shape(color: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(17).toFloat()
    }
    private fun txt(s: String, size: Float = 15f, color: Int = Color.WHITE, bold: Boolean = false) =
        TextView(this).apply {
            text = s
            textSize = size
            setTextColor(color)
            if (bold) typeface = Typeface.DEFAULT_BOLD
        }
    private fun label(info: ApplicationInfo) = try {
        BlackBoxCore.getPackageManager().getApplicationLabel(info).toString()
    } catch (_: Exception) { info.packageName }
    private fun icon(info: ApplicationInfo) = try {
        BlackBoxCore.getPackageManager().getApplicationIcon(info)
    } catch (_: Exception) { null }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        space = intent.getIntExtra("userID", 0)
        window.statusBarColor = bg
        window.navigationBarColor = bg
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(bg)
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(dp(18), bars.top + dp(14), dp(18), bars.bottom + dp(12))
            insets
        }
        setContentView(root)
        val bar = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        bar.addView(txt("‹", 35f, accent).apply {
            setPadding(dp(4), 0, dp(18), 0)
            setOnClickListener { finish() }
        })
        val heading = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        heading.addView(txt("Mes clones", 25f, Color.WHITE, true))
        heading.addView(txt("Espace " + (space + 1), 13f, muted))
        bar.addView(heading)
        root.addView(bar)

        count = txt("", 13f, muted)
        root.addView(count, LinearLayout.LayoutParams(-1, dp(48)))
        search = EditText(this).apply {
            hint = "Rechercher dans mes clones"
            setHintTextColor(muted)
            setTextColor(Color.WHITE)
            isSingleLine = true
            textSize = 15f
            setPadding(dp(16), dp(4), dp(16), dp(4))
            background = shape(surface)
        }
        root.addView(search, LinearLayout.LayoutParams(-1, dp(52)))
        val scroll = ScrollView(this)
        items = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(14), 0, 0)
        }
        scroll.addView(items)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val hint = txt("Arrêter, effacer ou supprimer un clone n'affecte pas l'application originale.", 12f, muted)
        root.addView(hint)
        search.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, n: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, n: Int) { reload() }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        reload()
    }

    override fun onResume() {
        super.onResume()
        if (this::items.isInitialized) reload()
    }

    private fun reload() {
        items.removeAllViews()
        val apps = try {
            BlackBoxCore.get().getInstalledApplications(0, space).sortedBy { label(it).lowercase() }
        } catch (e: Exception) {
            count.text = "Erreur de lecture"
            items.addView(txt(e.javaClass.simpleName, 14f, muted))
            return
        }
        count.text = "${apps.size} application(s) dans cet espace"
        val q = search.text?.toString().orEmpty()
        val shown = apps.filter { label(it).contains(q, true) || it.packageName.contains(q, true) }
        if (shown.isEmpty()) {
            items.addView(txt(if (apps.isEmpty()) "Aucun clone dans cet espace" else "Aucun résultat", 16f, muted))
        }
        for (app in shown) {
            val row = LinearLayout(this).apply {
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(13), dp(14), dp(13), dp(14))
                background = shape(surface)
                setOnClickListener { options(app) }
            }
            val image = ImageView(this).apply {
                setImageDrawable(icon(app))
                if (drawable == null) setImageResource(android.R.drawable.sym_def_app_icon)
            }
            row.addView(image, LinearLayout.LayoutParams(dp(48), dp(48)))
            val texts = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(12), 0, dp(8), 0)
            }
            texts.addView(txt(label(app), 16f, Color.WHITE, true))
            texts.addView(txt(app.packageName, 11f, muted))
            row.addView(texts, LinearLayout.LayoutParams(0, -2, 1f))
            row.addView(txt("Gérer", 14f, accent, true))
            val margin = LinearLayout.LayoutParams(-1, -2)
            margin.bottomMargin = dp(10)
            items.addView(row, margin)
        }
    }

    private fun options(info: ApplicationInfo) {
        AlertDialog.Builder(this).setTitle(label(info))
            .setItems(arrayOf("Ouvrir", "Arrêter", "Effacer les données", "Supprimer le clone", "Diagnostic du lancement")) { _, index ->
                when (index) {
                    0 -> runAction("Lancement demandé") {
                        if (!BlackBoxCore.get().launchApk(info.packageName, space)) {
                            diagnostic(info.packageName)
                        }
                    }
                    1 -> runAction("Clone arrêté") { BlackBoxCore.get().stopPackage(info.packageName, space) }
                    2 -> confirm("Effacer les données de " + label(info) + " ?") {
                        runAction("Données du clone effacées") { BlackBoxCore.get().clearPackage(info.packageName, space) }
                    }
                    3 -> confirm("Supprimer le clone " + label(info) + " ?") {
                        runAction("Clone supprimé") { BlackBoxCore.get().uninstallPackageAsUser(info.packageName, space) }
                    }
                    4 -> diagnostic(info.packageName)
                }
            }.setNegativeButton("Annuler", null).show()
    }

    private fun confirm(message: String, action: () -> Unit) {
        AlertDialog.Builder(this).setTitle("Confirmer l'opération")
            .setMessage(message + "\nCette action n'affecte pas l'application originale.")
            .setNegativeButton("Annuler", null)
            .setPositiveButton("Confirmer") { _, _ -> action() }.show()
    }

    private fun runAction(success: String, action: () -> Unit) {
        try {
            action()
            Toast.makeText(this, success, Toast.LENGTH_SHORT).show()
            reload()
        } catch (e: Exception) {
            AlertDialog.Builder(this).setTitle("Erreur")
                .setMessage(e.javaClass.simpleName + ": " + (e.message ?: "Échec"))
                .setPositiveButton("OK", null).show()
        }
    }

    private fun diagnostic(pkg: String) {
        val virtualInstalled = try { BlackBoxCore.get().isInstalled(pkg, space).toString() }
            catch (e: Exception) { e.javaClass.simpleName }
        val virtualIntent = try {
            BlackBoxCore.getBPackageManager().getLaunchIntentForPackage(pkg, space)
                ?.component?.flattenToShortString() ?: "introuvable"
        } catch (e: Exception) { "erreur " + e.javaClass.simpleName }
        val systemIntent = try {
            packageManager.getLaunchIntentForPackage(pkg)
                ?.component?.flattenToShortString() ?: "introuvable"
        } catch (e: Exception) { "erreur " + e.javaClass.simpleName }
        val splits = try {
            (packageManager.getApplicationInfo(pkg, 0).splitSourceDirs?.size ?: 0).toString()
        } catch (e: Exception) { e.javaClass.simpleName }
        val report = "Duova V4\nAPI Android : " + android.os.Build.VERSION.SDK_INT +
            "\nEspace : " + space + "\nPaquet : " + pkg + "\nClone installé : " + virtualInstalled +
            "\nActivité virtuelle : " + virtualIntent + "\nActivité Android : " + systemIntent +
            "\nAPK additionnels : " + splits
        AlertDialog.Builder(this).setTitle("Diagnostic de lancement").setMessage(report)
            .setNeutralButton("Copier") { _, _ ->
                val cb = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cb.setPrimaryClip(ClipData.newPlainText("Diagnostic Duova", report))
                Toast.makeText(this, "Diagnostic copié", Toast.LENGTH_SHORT).show()
            }.setPositiveButton("Fermer", null).show()
    }
}
