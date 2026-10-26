"""Tests de la tablette : profils d'appareil, lien UDP avec DCS, capture, kneeboards.

Le lien avec DCS est exercé avec de vraies sockets sur la boucle locale :
un faux script Lua reçoit les ordres et envoie les annonces, comme le ferait
`DCS-Tablette-Export.lua`. Les numéros des profils sont recoupés avec les
scripts des modules installés (ou leur copie dans le dépôt) quand ils sont là.
"""
import re
import socket
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tablette import appareils, planche  # noqa: E402
from tablette.appareils import a10c, ah64d, fa18c  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
DCS = Path("C:/Program Files (x86)/Steam/steamapps/common/DCSWorld")
SCRIPT_LUA = RACINE / "dcs_export" / "DCS-Tablette-Export.lua"
LUA_APPAREILS = RACINE / "dcs_export" / "DCS-Tablette-Appareils.lua"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
       b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def scripts_du_module(dossier: str):
    """Scripts cockpit du module installé, ou de sa copie dans le dépôt."""
    for chemin in (DCS / "Mods" / "aircraft" / dossier / "Cockpit" / "Scripts",
                   RACINE / dossier / "Cockpit" / "Scripts"):
        if chemin.is_dir():
            return chemin
    return None


def lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8", errors="replace")


def identifiants(scripts: Path, *noms):
    """Identifiants d'appareil : rang de déclaration dans devices.lua."""
    ordre = re.findall(r'devices\["(\w+)"\]\s*=\s*counter\(\)', lire(scripts / "devices.lua"))
    return {nom: ordre.index(nom) + 1 if nom in ordre else None for nom in noms}


def commandes(scripts: Path, table: str):
    """Numéros d'une table de command_defs.lua remise à start_command."""
    texte = lire(scripts / "command_defs.lua")
    debut = int(re.search(r"start_command\s*=\s*(\d+)", texte).group(1))
    avant, apres = texte.split(f"{table} =", 1)
    assert re.findall(r"count\s*=\s*([^\n]+)", avant)[-1].strip() == "start_command"
    noms = re.findall(r"(\w+)\s*=\s*counter\(\)", apres.split("}", 1)[0])
    return {nom: debut + i + 1 for i, nom in enumerate(noms)}


class TestProfils(unittest.TestCase):
    def test_ddi_du_hornet_dans_le_sens_horaire_depuis_le_bas_a_gauche(self):
        ddi = fa18c.PROFIL.ecran("ddi_gauche")
        attendu = {"1": ("gauche", 4), "5": ("gauche", 0), "6": ("haut", 0),
                   "10": ("haut", 4), "11": ("droite", 0), "15": ("droite", 4),
                   "16": ("bas", 4), "18": ("bas", 2), "20": ("bas", 0)}
        for id_, place in attendu.items():
            b = ddi.bouton(id_)
            self.assertEqual((b.cote, b.rang), place, id_)
        self.assertEqual((ddi.bouton("1").commande, ddi.bouton("20").commande), (3011, 3030))

    def test_mfcd_et_mfd_dans_le_sens_horaire_depuis_le_haut_a_gauche(self):
        for profil in (a10c.PROFIL, appareils.profil_pour("F-16C_50")):
            ecran = profil.ecrans[0]
            places = {b.id: (b.cote, b.rang) for b in ecran.boutons}
            self.assertEqual((places["1"], places["6"], places["11"], places["16"]),
                             (("haut", 0), ("droite", 0), ("bas", 4), ("gauche", 4)), profil.id)
            self.assertEqual(ecran.bouton("20").commande, 3020)

    def test_mpd_de_l_apache(self):
        mpd = ah64d.PROFIL.ecran("mpd_gauche")
        self.assertEqual((mpd.bouton("B1").cote, mpd.bouton("B1").rang), ("bas", 0))
        self.assertEqual((mpd.bouton("L1").cote, mpd.bouton("L1").rang), ("gauche", 0))
        self.assertEqual([mpd.bouton(i).commande for i in ("T1", "R6", "B6", "B1", "L6", "L1")],
                         [3001, 3012, 3013, 3018, 3019, 3024])
        self.assertEqual((mpd.appareil("pilote"), mpd.appareil("cpg")), (42, 44))

    def test_chaque_bouton_a_sa_place_et_son_nom(self):
        for profil in appareils.PROFILS:
            for ecran in profil.ecrans:
                places = [(b.cote, b.rang) for b in ecran.boutons]
                self.assertEqual(len(places), len(set(places)), (profil.id, ecran.id))
                ids = [b.id for b in ecran.boutons]
                self.assertEqual(len(ids), len(set(ids)), (profil.id, ecran.id))
                for b in ecran.boutons:
                    if b.cote != "rangee":
                        self.assertIn(b.cote, appareils.COTES)
                        self.assertLess(b.rang, ecran.par_cote, (profil.id, b))

    def test_profil_choisi_d_apres_le_nom_annonce_par_dcs(self):
        attendu = {"FA-18C_hornet": "fa18c", "F-16C_50": "f16c", "AH-64D_BLK_II": "ah64d",
                   "OH58D": "oh58d", "Mi-24P": "mi24p", "SA342M": "sa342", "SA342Mistral": "sa342",
                   "A-10C_2": "a10c", "MiG-29 Fulcrum": "mig29", "Su-25T": "fc3",
                   "Bf-109K-4": "generique", None: "generique"}
        for nom, id_ in attendu.items():
            self.assertEqual(appareils.profil_pour(nom).id, id_, nom)
        noms = [n for p in appareils.PROFILS for n in p.noms_dcs]
        self.assertEqual(len(noms), len(set(noms)))

    def test_zones_d_export_toutes_dans_la_configuration(self):
        from tablette.ecrans_dcs import EXPORTS
        self.assertLessEqual(set(appareils.viewports()), set(EXPORTS))

    def test_le_lua_genere_est_a_jour(self):
        self.assertEqual(lire(LUA_APPAREILS), appareils.lua_appareils(),
                         "relancer scripts/generer_lua_appareils.py")

    def test_la_liste_blanche_ne_mele_pas_les_appareils(self):
        lua = appareils.lua_appareils()
        hornet = lua.split('["FA-18C_hornet"]')[1].split('\n  },')[0]
        apache = lua.split('["AH-64D_BLK_II"]')[1].split('\n  },')[0]
        self.assertIn("[35] = {", hornet)
        self.assertIn("[25] = {", hornet)                     # l'UFC
        self.assertNotIn("[42] = {", hornet)
        self.assertIn("[42] = {", apache)
        self.assertIn("[44] = {", apache)                     # MPD du CPG
        self.assertNotIn("[35] = {", apache)
        self.assertIn("pages = { [68]", hornet)
        f16 = lua.split('["F-16C_50"]')[1].split('\n  },')[0]
        self.assertIn("pages = { }", f16)                     # kneeboard non relevé
        self.assertIn('TABLETTE_APPAREILS', lire(SCRIPT_LUA))
        self.assertIn('DCS-Tablette-Appareils.lua', lire(SCRIPT_LUA))


class TestContreLesScriptsDesModules(unittest.TestCase):
    """Une mise à jour de DCS qui décalerait les listes doit se voir ici."""

    def module(self, dossier):
        scripts = scripts_du_module(dossier)
        if scripts is None:
            self.skipTest(f"module {dossier} absent")
        return scripts

    def test_hornet(self):
        s = self.module("FA-18C")
        self.assertEqual(identifiants(s, "MDI_LEFT", "MDI_RIGHT", "AMPCD", "KNEEBOARD", "UFC"),
                         {"MDI_LEFT": 35, "MDI_RIGHT": 36, "AMPCD": 37,
                          "KNEEBOARD": fa18c.PROFIL.kneeboard, "UFC": planche.UFC})
        ufc = commandes(s, "UFC_commands")
        self.assertEqual(ufc["KbdSwENT"], planche.TOUCHES_UFC["ENT"])
        self.assertEqual(ufc["FuncSwAP"], planche.TOUCHES_UFC["AP"])
        self.assertEqual(ufc["Comm1Ch"], planche.MOLETTES_UFC["COMM1"])
        texte = lire(s / "command_defs.lua").split("MDI/AMPCD Pushbuttons")[1][:400]
        self.assertRegex(texte, r"count = start_command \+ 10")
        # Les tables des aiguilles, telles que mainpanel_init.lua les déclare.
        panneau = lire(s / "mainpanel_init.lua")
        bloc = panneau.split("Airspeed.arg_number")[1][:400]
        self.assertIn(f"= {planche.BADIN[0]}", bloc.split("\n")[0])
        lampes = lire(s / "MainPanel" / "lamps.lua")
        for nom, lampe in (("MASTER CAUTION", "MASTER_CAUTION"), ("FIRE G", "FIRE_LEFT"),
                           ("NOSE", "NOSE_GEAR"), ("HOOK", "HOOK")):
            motif = rf"create_caution_lamp\({planche.VOYANTS[nom]},\s*CautionLights\.CPT_LTS_{lampe}\)"
            self.assertTrue(re.search(motif, lampes), nom)

    def test_apache(self):
        s = self.module("AH-64D")
        self.assertEqual(identifiants(s, "MFD_PLT_LEFT", "MFD_PLT_RIGHT", "MFD_CPG_LEFT",
                                      "MFD_CPG_RIGHT", "KNEEBOARD"),
                         {"MFD_PLT_LEFT": 42, "MFD_PLT_RIGHT": 43, "MFD_CPG_LEFT": 44,
                          "MFD_CPG_RIGHT": 45, "KNEEBOARD": ah64d.PROFIL.kneeboard})
        mpd = commandes(s, "mpd_commands")
        ecran = ah64d.PROFIL.ecran("mpd_gauche")
        for nom, id_ in (("T1", "T1"), ("B1", "B1"), ("L6", "L6"), ("AC", "A/C"),
                         ("Asterisk", "*"), ("FCR", "FCR")):
            self.assertEqual(mpd[nom], ecran.bouton(id_).commande, nom)

    def test_a10c(self):
        s = self.module("A-10C_2")
        self.assertEqual(identifiants(s, "MFCD_LEFT", "MFCD_RIGHT", "KNEEBOARD"),
                         {"MFCD_LEFT": 2, "MFCD_RIGHT": 3, "KNEEBOARD": None})
        self.assertRegex(lire(s / "command_defs.lua"), r"Button_1\s*=\s*start_command \+ 1;")
        commun = DCS / "Scripts" / "Aircrafts" / "_Common" / "Cockpit" / "KNEEBOARD"
        self.assertIn("devices.KNEEBOARD or 100", lire(commun / "declare_kneeboard_device.lua"))
        self.assertEqual(a10c.PROFIL.kneeboard, 100)

    def test_appareils_sans_ecran(self):
        for dossier, nom in (("MiG-29-Fulcrum", "MiG-29 Fulcrum"), ("TF-51D", "TF-51D")):
            s = scripts_du_module(dossier)
            if s is None:
                continue
            self.assertEqual(identifiants(s, "KNEEBOARD")["KNEEBOARD"],
                             appareils.profil_pour(nom).kneeboard, dossier)

    def test_commandes_de_page_communes(self):
        texte = DCS / "Config" / "Input" / "Aircrafts" / "common_keyboard_binding.lua"
        if not texte.exists():
            self.skipTest("DCS absent")
        texte = lire(texte)
        self.assertRegex(texte, r"down = 3001,\s*cockpit_device_id = kneeboard_id.*Next Page")
        self.assertRegex(texte, r"down = 3002,\s*cockpit_device_id = kneeboard_id.*Previous Page")
        self.assertIn("local kneeboard_id = 100", texte)


class TestPlanche(unittest.TestCase):
    TEXTE_UFC = ("-----------------------------------------\nUFC_MainDummy\n\n"
                 "-----------------------------------------\nUFC_mask\n\n"
                 "-----------------------------------------\nUFC_ScratchPadString1Display\nC\n"
                 "-----------------------------------------\nUFC_ScratchPadNumberDisplay\n"
                 "  127.500\n"
                 "-----------------------------------------\nUFC_OptionCueing1\n:\n"
                 "-----------------------------------------\nUFC_OptionDisplay1\nTR  \n"
                 "-----------------------------------------\nUFC_Comm1Display\n`1\n"
                 "children are {\n}\n")

    def test_texte_des_ecrans_lu_par_champ(self):
        champs = planche.lire_indication(self.TEXTE_UFC)
        self.assertEqual(champs["UFC_ScratchPadNumberDisplay"], "  127.500")
        self.assertEqual(champs["UFC_Comm1Display"], "`1")
        ufc = planche.ufc(champs)
        self.assertEqual(ufc["bloc"], ["C", "", "  127.500"])
        self.assertEqual(ufc["options"][0], {"repere": ":", "texte": "TR"})
        self.assertEqual(ufc["comm1"], "`1")
        self.assertEqual(planche.lire_indication("MENU_1__id:1\nMENU\n"), {"MENU_1": "MENU"})

    def test_aiguilles_lues_avec_les_tables_du_cockpit(self):
        args = {217: 0.586, 225: 0.22, 218: 0.5, 219: 0.3, 220: 1 / 9, 205: 0.5, 206: -0.5,
                242: 0.636, 310: 0.6, 311: 0.6, 13: 1.0, 10: 0.0}
        instr = planche.instruments(args)
        self.assertEqual(instr["badin"]["valeur"], 200.0)
        self.assertEqual(instr["vario"]["valeur"], 500.0)
        self.assertEqual(instr["altimetre"]["valeur"], 13500)
        self.assertEqual((instr["sai"]["assiette"], instr["sai"]["inclinaison"]), (45.0, -90.0))
        self.assertEqual(instr["frein"]["valeur"], 3000.0)
        voyants = planche.voyants(args)
        self.assertTrue(voyants["MASTER CAUTION"])
        self.assertFalse(voyants["FIRE G"])
        self.assertIsNone(planche.instruments({}))

    def test_graduations_placees_avec_les_memes_tables(self):
        cadrans = planche.cadrans()
        badin = {g["texte"]: g["angle"] for g in cadrans["badin"]["graduations"]}
        self.assertAlmostEqual(badin["200"], 0.586 * 360, places=0)
        vario = {g["angle"] for g in cadrans["vario"]["graduations"] if g["texte"] == "0"}
        self.assertEqual(vario, {270.0})


class TestConfigurationEcransDCS(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def options(self, choix, largeur=2560, hauteur=1440):
        (self.saved / "Config" / "options.lua").write_text(
            'options = {\n\t["graphics"] = {\n'
            f'\t\t["aspect"] = {largeur / hauteur:.14g},\n'
            f'\t\t["fullScreen"] = false,\n\t\t["height"] = {hauteur},\n'
            f'\t\t["multiMonitorSetup"] = "{choix}",\n\t\t["width"] = {largeur},\n'
            '\t},\n}\n', encoding="utf-8")

    def test_le_fichier_genere_se_relit_a_l_identique(self):
        from tablette.ecrans_dcs import (disposition_essai, disposition_second_ecran,
                                         generer, lire_zones)
        for vue, zones in (((0, 0, 2560, 1440), disposition_essai(2560, 1440)),
                           ((0, 0, 2560, 1440),
                            disposition_second_ecran(2560, 1440, 1920, 1080))):
            texte = generer(vue, zones, "test")
            texte.encode("ascii")
            self.assertEqual(lire_zones(texte, 4480, 1440), zones)

    def test_apostrophe_echappee_dans_les_chaines_lua(self):
        from tablette.ecrans_dcs import generer
        texte = generer((0, 0, 100, 100), {}, "Vue sur l'ecran principal")
        self.assertIn(r"Description = 'Vue sur l\'ecran principal'", texte)
        # Chaque ligne a un nombre pair d'apostrophes non échappées.
        for ligne in texte.splitlines():
            self.assertEqual(ligne.replace(r"\'", "").count("'") % 2, 0, ligne)

    def test_dispositions(self):
        from tablette.ecrans_dcs import disposition_essai, disposition_second_ecran
        self.assertEqual(disposition_essai(2560, 1440),
                         {"LEFT_MFCD": (0, 960, 480, 480), "CENTER_MFCD": (800, 960, 480, 480),
                          "TEDAC": (1280, 960, 480, 480), "RIGHT_MFCD": (2080, 960, 480, 480)})
        # Écran virtuel 2560 × 1440 : gauche et droit en haut, central et TEDAC
        # dessous, coin bas droit laissé au kneeboard.
        self.assertEqual(disposition_second_ecran(2560, 1440, 2560, 1440),
                         {"LEFT_MFCD": (2560, 0, 720, 720), "RIGHT_MFCD": (3280, 0, 720, 720),
                          "CENTER_MFCD": (2560, 720, 720, 720), "TEDAC": (3280, 720, 720, 720)})

    def test_dcs_regle_dans_options_lua_avec_une_copie(self):
        from tablette.ecrans_dcs import regler_options
        self.options("1camera")
        copie = regler_options(self.saved, 5120, 1440)
        texte = lire(self.saved / "Config" / "options.lua")
        for attendu in ('["multiMonitorSetup"] = "tablette",', '["width"] = 5120,',
                        '["height"] = 1440,', '["fullScreen"] = false,',
                        '["aspect"] = 3.5555555555556,'):
            self.assertIn(attendu, texte)
        self.assertIn('"1camera"', lire(copie))

    def test_le_kneeboard_ne_recouvre_aucun_ecran(self):
        """Mesuré en vrai le 25/10/2026 en 5120 × 1440 : cadre du kneeboard de
        x = 4368 à 5120 et de y = 356 à 1440, page 720 × 1080."""
        from tablette.ecrans_dcs import (BANDEAU_KNEEBOARD, disposition_second_ecran,
                                         zone_kneeboard)
        self.assertEqual(zone_kneeboard(5120, 1440), (4400, 356, 720, 1084))
        self.assertEqual(zone_kneeboard(2560, 1440), (1840, 356, 720, 1084))
        for principal, second in (((2560, 1440), (2560, 1440)), ((2560, 1440), (1920, 1080)),
                                  ((1920, 1080), (1920, 1080))):
            largeur_totale = principal[0] + second[0]
            kx, ky, kl, kh = zone_kneeboard(largeur_totale, max(principal[1], second[1]))
            cadre = (kx - BANDEAU_KNEEBOARD, ky, kl + BANDEAU_KNEEBOARD, kh)
            for nom, (x, y, l, h) in disposition_second_ecran(*principal, *second).items():
                separes = (x + l <= cadre[0] or cadre[0] + cadre[2] <= x
                           or y + h <= cadre[1] or cadre[1] + cadre[3] <= y)
                self.assertTrue(separes, (principal, second, nom))
                self.assertGreaterEqual(x, principal[0], nom)        # sur le second
                self.assertLessEqual(x + l, largeur_totale, nom)


    def test_expressions_des_fichiers_livres_avec_dcs(self):
        from tablette.ecrans_dcs import lire_zones
        texte = ("LEFT_MFCD =\n{\n     x = 0;\n     y = 0;\n     width = screen.width / 3;\n"
                 "     height = screen.height;\n}\nRIGHT_MFCD =\n{\n"
                 "     x = screen.width *(2 / 3);\n     y = 0;\n"
                 "     width = screen.width / 3;\n     height = screen.height;\n}\n")
        self.assertEqual(lire_zones(texte, 3840, 1080),
                         {"LEFT_MFCD": (0, 0, 1280, 1080), "RIGHT_MFCD": (2560, 0, 1280, 1080)})
        self.assertEqual(lire_zones("LEFT_MFCD = { x = os.exit(); y = 0; width = 1; "
                                    "height = 1; }", 100, 100), {})

    def test_configuration_choisie_dans_dcs(self):
        from tablette.ecrans_dcs import (NOM_FICHIER, PasDExport, disposition_essai,
                                         generer, zones_actives)
        zones = disposition_essai(2560, 1440)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), zones, "test"), encoding="ascii")
        self.options("tablette")
        self.assertEqual(zones_actives(self.saved), zones)
        self.options("Tablette DCS")       # désignée par son nom affiché
        self.assertEqual(zones_actives(self.saved), zones)
        self.options("1camera")
        with self.assertRaises(PasDExport) as e:
            zones_actives(self.saved)
        self.assertIn("Tablette DCS", str(e.exception))

    def test_la_copie_d_origine_survit_a_une_seconde_installation(self):
        from tablette.ecrans_dcs import regler_options, retablir_options
        self.options("1camera", 1920, 1080)
        regler_options(self.saved, 5120, 1440)
        copie = regler_options(self.saved, 4480, 1440)
        self.assertIn('"1camera"', lire(copie))
        # Un réglage changé depuis reste ; l'affichage revient seul.
        options = self.saved / "Config" / "options.lua"
        options.write_text(lire(options).replace('["graphics"] = {',
                                                 '["graphics"] = {\n\t\t["vsync"] = true,'),
                           encoding="utf-8")
        retablir_options(self.saved)
        texte = lire(options)
        for attendu in ('["multiMonitorSetup"] = "1camera",', '["width"] = 1920,',
                        '["height"] = 1080,', '["vsync"] = true,'):
            self.assertIn(attendu, texte)


class TestInstallation(unittest.TestCase):
    """Ce que fait `DCS-Tablette.exe installer` / `desinstaller`, dans un faux
    Saved Games/DCS : jamais celui du poste."""

    PRINCIPAL = (0, 0, 2560, 1440, True)
    VIRTUEL = (2560, 0, 2560, 1440, False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Scripts").mkdir()
        (self.saved / "Config").mkdir()
        (self.saved / "Config" / "options.lua").write_text(
            'options = {\n\t["graphics"] = {\n\t\t["aspect"] = 1.7777777777778,\n'
            '\t\t["fullScreen"] = true,\n\t\t["height"] = 1440,\n'
            '\t\t["multiMonitorSetup"] = "1camera",\n\t\t["width"] = 2560,\n\t},\n}\n',
            encoding="utf-8")
        self.export = self.saved / "Scripts" / "Export.lua"
        # Un Export.lua d'un autre outil, pas en UTF-8 et sans fin de ligne.
        self.export.write_bytes(b"dofile(lfs.writedir()..'Scripts/TacviewGameExport.lua') -- \xe9")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scripts_installes_une_fois_puis_retires(self):
        from tablette.installation import (LIGNE, SCRIPTS, desinstaller_scripts, est_installe,
                                           installer_scripts)
        origine = self.export.read_bytes()
        self.assertFalse(est_installe(self.saved))
        installer_scripts(self.saved)
        lignes = installer_scripts(self.saved)
        self.assertIn("Export.lua charge déjà la tablette.", lignes)
        self.assertTrue(est_installe(self.saved))
        texte = self.export.read_bytes()
        self.assertTrue(texte.startswith(origine + b"\n"))
        self.assertEqual(texte.count(LIGNE.encode()), 1)
        for nom in SCRIPTS:
            self.assertEqual((self.saved / "Scripts" / nom).read_bytes(),
                             (RACINE / "dcs_export" / nom).read_bytes())
        self.assertEqual(len(list((self.saved / "Scripts").glob("Export.lua.avant-tablette-*"))), 1)

        desinstaller_scripts(self.saved)
        self.assertEqual(self.export.read_bytes(), origine + b"\n")
        self.assertFalse(est_installe(self.saved))
        for nom in SCRIPTS:
            self.assertFalse((self.saved / "Scripts" / nom).exists())

    def test_ecrans_sur_l_ecran_virtuel_puis_retires(self):
        from tablette.ecrans_dcs import NOM_FICHIER, options_affichage, zones_actives
        from tablette.installation import configurer_ecrans, retirer_ecrans
        complet, _ = configurer_ecrans(self.saved, ecrans=[self.PRINCIPAL, self.VIRTUEL],
                                       ouvert=lambda: False)
        self.assertTrue(complet)
        self.assertEqual(options_affichage(self.saved), ("tablette", 5120, 1440))
        self.assertEqual(zones_actives(self.saved)["LEFT_MFCD"], (2560, 0, 720, 720))

        self.assertIn("DCS est ouvert", retirer_ecrans(self.saved, ouvert=lambda: True)[0])
        retirer_ecrans(self.saved, ouvert=lambda: False)
        self.assertEqual(options_affichage(self.saved), ("1camera", 2560, 1440))
        self.assertIn('["fullScreen"] = true,', lire(self.saved / "Config" / "options.lua"))
        self.assertFalse((self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).exists())

    def test_sans_second_ecran_rien_n_est_ecrit(self):
        from tablette.installation import configurer_ecrans
        # Un écran à gauche du principal ne convient pas : DCS s'étend vers la droite.
        a_gauche = (-1920, 0, 1920, 1080, False)
        for ecrans in ([self.PRINCIPAL], [self.PRINCIPAL, a_gauche]):
            complet, lignes = configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: False)
            self.assertFalse(complet)
            self.assertIn("Virtual Display Driver", "\n".join(lignes))
        self.assertFalse((self.saved / "Config" / "MonitorSetup").exists())
        self.assertIn('"1camera"', lire(self.saved / "Config" / "options.lua"))

    @unittest.skipUnless(sys.platform == "win32", "raccourci Windows")
    def test_raccourci_vers_l_executable(self):
        from tablette.installation import RACCOURCI, creer_raccourci
        lien = creer_raccourci(Path(sys.executable), self.saved)
        self.assertEqual(lien, self.saved / RACCOURCI)
        self.assertTrue(lien.read_bytes().startswith(b"L\x00\x00\x00"))   # en-tête d'un .lnk

    def test_mise_a_jour_dcs_ouvert_configuration_identique_intacte(self):
        """Réécrite DCS ouvert, la configuration paraîtrait changée depuis son
        lancement et la tablette ne capturerait plus rien."""
        from tablette.ecrans_dcs import NOM_FICHIER
        from tablette.installation import configurer_ecrans
        ecrans = [self.PRINCIPAL, self.VIRTUEL]
        configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: False)
        fichier = self.saved / "Config" / "MonitorSetup" / NOM_FICHIER
        avant = fichier.stat().st_mtime_ns
        complet, lignes = configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: True)
        self.assertTrue(complet)
        self.assertTrue(lignes[0].startswith("Inchangé"))
        self.assertTrue(lignes[-1].startswith("DCS déjà réglé"))   # pas de « relance DCS »
        self.assertEqual(fichier.stat().st_mtime_ns, avant)
        self.assertFalse(fichier.with_suffix(".lua.precedent").exists())

    def test_dcs_ouvert_options_lua_intact(self):
        from tablette.installation import configurer_ecrans
        avant = lire(self.saved / "Config" / "options.lua")
        complet, lignes = configurer_ecrans(self.saved, ecrans=[self.PRINCIPAL, self.VIRTUEL],
                                            ouvert=lambda: True)
        self.assertTrue(complet)
        self.assertEqual(lire(self.saved / "Config" / "options.lua"), avant)
        self.assertIn("5120×1440", "\n".join(lignes))


class TestVideo(unittest.TestCase):
    """La capture est remplacée par une fausse : on vérifie ce qu'on en fait."""

    def setUp(self):
        from PIL import Image

        from tablette.ecrans_dcs import NOM_FICHIER, disposition_essai, generer

        self.Image = Image
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), disposition_essai(2560, 1440), "test"),
            encoding="ascii")
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 1440,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 2560,\n', encoding="utf-8")
        self.taille = (2560, 1440)
        self.absente = False
        self.captures = 0
        self.couleur = (40, 200, 60)      # le fond de l'écran exporté
        self.cockpit = (150, 150, 150)    # le liseré que DCS laisse autour
        self.vue = (90, 90, 90)           # le reste de la fenêtre
        self.instant = 0.0
        self.lancement = None             # DCS « lancé » : heure, ou None

    def tearDown(self):
        self.tmp.cleanup()

    def video(self):
        from PIL import ImageDraw

        from tablette.copie import decouper
        from tablette.ecrans_dcs import disposition_essai
        from tablette.video import Video

        def capturer(zones):
            self.captures += 1
            self.dernieres = set(zones)
            if self.absente:
                return None
            fenetre = self.Image.new("RGB", self.taille, self.vue)
            dessin = ImageDraw.Draw(fenetre)
            for x, y, l, h in disposition_essai(2560, 1440).values():
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=self.couleur,
                                 outline=self.cockpit, width=4)
            return decouper(fenetre, zones)

        return Video(self.saved, capturer=capturer, lancement=lambda: self.lancement,
                     horloge=lambda: self.instant)

    def decoder(self, donnees):
        import io
        self.assertEqual(donnees[:3], b"\xff\xd8\xff")
        return self.Image.open(io.BytesIO(donnees)).convert("RGB")

    def test_ecran_decoupe_sans_le_liseré_du_cockpit(self):
        image = self.decoder(self.video().image("LEFT_MFCD"))
        self.assertEqual(image.size, (468, 468))          # 6 px rognés par bord
        for coin in ((0, 0), (467, 0), (0, 467), (467, 467)):
            r, v, b = image.getpixel(coin)
            self.assertLess(abs(v - 200) + abs(r - 40), 40, coin)

    def test_une_copie_sert_tous_les_ecrans_affiches(self):
        video = self.video()
        for viewport in ("LEFT_MFCD", "RIGHT_MFCD", "CENTER_MFCD"):
            video.image(viewport)              # la page démarre : chacun se présente
        self.instant += 0.1
        self.captures = 0
        for viewport in ("LEFT_MFCD", "RIGHT_MFCD", "CENTER_MFCD", "LEFT_MFCD"):
            video.image(viewport)
        self.assertEqual(self.captures, 1)

    def test_seuls_les_ecrans_affiches_sont_copies(self):
        video = self.video()
        video.image("CENTER_MFCD")             # l'AMPCD, affiché un moment…
        for _ in range(3):                     # …puis la page passe aux deux DDI
            self.instant += 0.6
            video.image("LEFT_MFCD")
            video.image("RIGHT_MFCD")
        self.assertEqual(self.dernieres, {"LEFT_MFCD", "RIGHT_MFCD"})

    def test_temoin_copie_seulement_pour_un_ecran_noir(self):
        video = self.video()
        video.image("LEFT_MFCD")
        self.assertEqual(self.captures, 1)
        self.couleur = self.cockpit = (0, 0, 0)
        self.instant += 0.1
        video.image("LEFT_MFCD")
        self.assertEqual(self.captures, 3)     # la copie, puis le témoin
        self.assertEqual(self.dernieres, {"TEMOIN"})

    def test_ecran_eteint_servi_mais_capture_aveugle_signalee(self):
        from tablette.video import PasDImage
        self.couleur = self.cockpit = (0, 0, 0)
        self.decoder(self.video().image("CENTER_MFCD"))
        self.vue = (0, 0, 0)
        with self.assertRaises(PasDImage) as e:
            self.video().image("CENTER_MFCD")
        self.assertIn("Plein écran", str(e.exception))

    def test_raisons_sans_image(self):
        from tablette.video import PasDImage
        self.absente = True
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("pas lancé", str(e.exception))
        self.absente = False
        # Configuration d'écrans qui ne correspond plus à la fenêtre.
        from tablette.ecrans_dcs import NOM_FICHIER, generer
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), {"RIGHT_MFCD": (0, 1440, 800, 800)}, "test"),
            encoding="ascii")
        with self.assertRaises(PasDImage) as e:
            self.video().image("RIGHT_MFCD")
        self.assertIn("sort de la fenêtre", str(e.exception))

    def test_configuration_reecrite_apres_le_lancement_de_dcs(self):
        """Vu en vrai : réécrite pendant que DCS tournait, la configuration ne
        disait plus où DCS dessinait, et l'iPad montrait n'importe quoi."""
        import os

        from tablette.ecrans_dcs import NOM_FICHIER
        from tablette.video import PasDImage
        fichier = self.saved / "Config" / "MonitorSetup" / NOM_FICHIER
        os.utime(fichier, (1_000_000, 1_000_000))
        self.lancement = 2_000_000.0                    # DCS lancé après : bon
        self.video().image("LEFT_MFCD")
        self.lancement = 500_000.0                      # DCS lancé avant : non
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("relance DCS", str(e.exception))

    def test_fenetre_plus_petite_que_la_resolution_reglee(self):
        """Vu en vrai : DCS réglé en 2560 × 2240 sur un écran de 1440 de haut
        garde une fenêtre de 2560 × 1440 ; le dire tel quel."""
        from tablette.video import PasDImage
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 2240,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 2560,\n', encoding="utf-8")
        from tablette.ecrans_dcs import NOM_FICHIER, generer
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), {"LEFT_MFCD": (0, 1440, 800, 800)}, "test"),
            encoding="ascii")
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("réglé en 2560 × 2240 mais sa fenêtre ne fait que 2560 × 1440",
                      str(e.exception))


class TestKneeboardDCS(unittest.TestCase):
    """Écran virtuel à droite : DCS ouvre le kneeboard sur lui, on le capture."""

    def setUp(self):
        from PIL import Image

        from tablette.ecrans_dcs import NOM_FICHIER, disposition_second_ecran, generer

        self.Image = Image
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)
        self.zones = disposition_second_ecran(2560, 1440, 2560, 1440)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), self.zones, "test"), encoding="ascii")
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 1440,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 5120,\n', encoding="utf-8")
        self.ouvert = True

    def tearDown(self):
        self.tmp.cleanup()

    def video(self):
        from PIL import ImageDraw

        from tablette.copie import decouper
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.video import Video

        def capturer(zones):
            fenetre = self.Image.new("RGB", (5120, 1440), (0, 0, 0))
            dessin = ImageDraw.Draw(fenetre)
            dessin.rectangle((0, 0, 2559, 1439), fill=(90, 90, 90))      # la vue
            for x, y, l, h in self.zones.values():
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=(40, 200, 60))
            if self.ouvert:
                x, y, l, h = zone_kneeboard(5120, 1440)
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=(250, 240, 150))
            return decouper(fenetre, zones)

        return Video(self.saved, capturer=capturer, lancement=lambda: None)

    def test_page_ouverte_capturee_entiere(self):
        page = self.video().kneeboard()
        self.assertEqual(page.size, (720, 1084))
        self.assertEqual(page.getpixel((360, 540)), (250, 240, 150))

    def test_kneeboard_ferme_dit_comment_l_ouvrir(self):
        from tablette.video import PasDImage
        self.ouvert = False
        with self.assertRaises(PasDImage) as e:
            self.video().image("KNEEBOARD")
        self.assertIn("RShift+K", str(e.exception))

    def test_ecran_debordant_ne_fait_pas_croire_le_kneeboard_ouvert(self):
        """Vu en vrai : avec l'ancienne disposition encore chargée par DCS, le
        DDI droit couvrait le haut de la zone ; le miroir montrait ce DDI."""
        from tablette.video import PasDImage
        self.ouvert = False
        self.zones["RIGHT_MFCD"] = (4266, 0, 853, 853)
        with self.assertRaises(PasDImage):
            self.video().kneeboard()

    def test_les_ddi_restent_intacts_kneeboard_ouvert(self):
        import io
        image = self.Image.open(io.BytesIO(self.video().image("RIGHT_MFCD")))
        r, v, b = image.convert("RGB").getpixel((image.width - 2, image.height - 2))
        self.assertLess(abs(v - 200) + abs(r - 40), 40)


class TestMiroir(unittest.TestCase):
    def test_miroir_seulement_si_le_kneeboard_quitte_l_ecran_principal(self):
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.miroir import hors_ecran_principal
        principal = (0, 0, 2560, 1440)
        self.assertTrue(hors_ecran_principal(zone_kneeboard(5120, 1440), principal))
        self.assertFalse(hors_ecran_principal(zone_kneeboard(2560, 1440), principal))

    def test_place_la_ou_dcs_l_aurait_mis_sur_un_ecran_unique(self):
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.miroir import place_miroir
        self.assertEqual(place_miroir((0, 0, 2560, 1440), (720, 1084)),
                         zone_kneeboard(2560, 1440))
        # Barre des tâches de 48 px en bas : le miroir se pose au-dessus.
        self.assertEqual(place_miroir((0, 0, 2560, 1392), (720, 1084)),
                         (1840, 308, 720, 1084))

    def test_kneeboard_rendu_au_pc_quand_la_tablette_se_tait(self):
        from tablette.miroir import AffichageKneeboard, Miroir
        maintenant = [100.0]
        affichage = AffichageKneeboard(horloge=lambda: maintenant[0])
        miroir = Miroir(video=None, saved_games=Path("."), affichage=affichage)
        self.assertTrue(miroir._sur_pc())
        affichage.choisir("tablette")
        self.assertFalse(miroir._sur_pc())
        maintenant[0] += 9
        self.assertEqual(affichage.effectif(), "tablette")
        maintenant[0] += 2                  # 11 s sans nouvelles de la tablette
        self.assertEqual(affichage.effectif(), "pc")
        affichage.choisir("ailleurs")       # ignoré
        self.assertEqual(affichage.effectif(), "pc")


class FauxLua:
    """Joue le rôle de DCS-Tablette-Export.lua sur des ports éphémères."""

    def __init__(self):
        self.ecoute = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.settimeout(2)
        self.port = self.ecoute.getsockname()[1]

    def recevoir(self) -> str:
        return self.ecoute.recvfrom(64)[0].decode("ascii")

    def annoncer(self, port_etat: int, nom: str) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(f"etat {nom}".encode(), ("127.0.0.1", port_etat))
        s.close()

    def fermer(self):
        self.ecoute.close()


class TestApiTablette(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        from tablette.dcs import PontDCS

        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        self.lua = FauxLua()
        self.pont = PontDCS(port_ordres=self.lua.port, port_etat=0)
        self.pont.demarrer()
        cfg = Config(saved_games=self.saved)
        self.dossier_dcs = None             # le DCS du poste n'entre pas dans les tests
        self.client = TestClient(create_app(cfg, self.pont,
                                            dossier_dcs=lambda: self.dossier_dcs))

    def tearDown(self):
        self.pont.arreter()
        self.lua.fermer()
        self.tmp.cleanup()

    def bouton(self, ecran, bouton, enfonce=True, **autres):
        return self.client.post("/api/bouton", json={"ecran": ecran, "bouton": bouton,
                                                     "enfonce": enfonce, **autres})

    def piloter(self, nom):
        """Fait annoncer `nom` par le faux script, et attend que le serveur suive."""
        self.lua.annoncer(self.pont.port_etat, nom)
        for _ in range(100):
            if self.client.get("/api/etat").json()["dcs"]["appareil"] == nom:
                return
            time.sleep(0.02)
        self.fail(f"{nom} jamais annoncé")

    def silence(self):
        self.lua.ecoute.settimeout(0.3)
        with self.assertRaises(socket.timeout):
            self.lua.recevoir()

    def test_appareil_choisi_a_la_main_et_garde_fou(self):
        """Le menu de la tablette (cookie) prépare la page avant la mission ;
        mais rien ne part vers un DCS qui pilote autre chose : l'OSB 1 du MFD
        droit du F-16 y serait l'A/P de l'UFC du Hornet."""
        self.assertIn("ah64d", [p["id"] for p in self.client.get("/api/profils").json()])
        self.client.cookies.set("tablette_appareil", "ah64d")
        self.assertEqual(self.client.get("/api/profil").json()["id"], "ah64d")
        e = self.client.get("/api/etat").json()
        self.assertEqual((e["profil"], e["choisi"], e["ailleurs"]), ("ah64d", True, None))

        self.piloter("FA-18C_hornet")
        e = self.client.get("/api/etat").json()
        self.assertEqual((e["profil"], e["ailleurs"]), ("ah64d", "F/A-18C Hornet"))
        r = self.bouton("mpd_gauche", "T1")
        self.assertEqual(r.status_code, 409)
        self.assertIn("boutons coupés", r.json()["detail"])
        self.silence()

        self.piloter("AH-64D_BLK_II")
        self.assertEqual(self.bouton("mpd_gauche", "T1").json(), {"envoye": True})
        self.assertEqual(self.lua.recevoir(), "42 3001 1")

        # Hornet choisi, F-16 piloté : l'UFC non plus ne part pas.
        self.client.cookies.set("tablette_appareil", "fa18c")
        self.piloter("F-16C_50")
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "AP", "enfonce": True})
                         .status_code, 409)
        self.silence()
        # Auto : la page suit de nouveau DCS.
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/profil").json()["id"], "f16c")

    def test_coins_des_ecrans_selon_l_appareil(self):
        """Arrondis mesurés sur le Hornet seulement ; l'Apache est quasi carré."""
        hornet = appareils.profil_par_id("fa18c").description()["ecrans"]
        apache = appareils.profil_par_id("ah64d").description()["ecrans"]
        self.assertEqual({e["arrondi"] for e in hornet}, {0.17})
        self.assertTrue(all(e["arrondi"] <= 0.02 for e in apache))

    def test_page_installable_sur_l_ecran_d_accueil(self):
        """Android lit le manifeste, iOS l'icône 180 : nom, icône, plein écran."""
        page = self.client.get("/").text
        self.assertIn('href="/manifest.webmanifest"', page)
        self.assertIn('href="/icone-180.png"', page)
        manifeste = self.client.get("/manifest.webmanifest").json()
        self.assertEqual(manifeste["display"], "fullscreen")
        for icone in manifeste["icons"] + [{"src": "/icone-180.png"}]:
            r = self.client.get(icone["src"])
            self.assertEqual(r.status_code, 200, icone["src"])
            self.assertTrue(r.content.startswith(b"\x89PNG"), icone["src"])
        self.assertEqual(self.client.get("/icone-64.png").status_code, 404)

    def test_appui_puis_relachement_arrivent_au_script(self):
        self.assertEqual(self.bouton("ddi_gauche", "18").json(), {"envoye": True})
        self.assertEqual(self.lua.recevoir(), "35 3028 1")
        self.bouton("ddi_gauche", "18", enfonce=False)
        self.assertEqual(self.lua.recevoir(), "35 3028 0")

    def test_chaque_appui_est_ecrit_dans_le_journal(self):
        with self.assertLogs("tablette", level="INFO") as journal:
            self.bouton("ddi_droit", "7")
        self.lua.recevoir()
        self.assertEqual(len(journal.output), 1)
        # Sans annonce du script, l'ordre part mais personne ne l'écoute.
        self.assertIn("DDI droit 7 enfoncé — DCS ne répond pas", journal.output[0])

    def test_ampcd_et_ddi_droit(self):
        self.bouton("ampcd", "1")
        self.assertEqual(self.lua.recevoir(), "37 3011 1")
        self.bouton("ddi_droit", "20")
        self.assertEqual(self.lua.recevoir(), "36 3030 1")

    def test_ordres_invalides_refuses_sans_rien_envoyer(self):
        self.assertEqual(self.bouton("hud", "1").status_code, 404)
        for b in ("0", "21", "x", None):
            self.assertEqual(self.bouton("ddi_gauche", b).status_code, 422, b)
        self.silence()

    def test_le_profil_suit_l_appareil_et_le_siege(self):
        self.assertEqual(self.client.get("/api/profil").json()["id"], "fa18c")
        self.piloter("AH-64D_BLK_II")
        profil = self.client.get("/api/profil").json()
        self.assertEqual((profil["id"], profil["sieges"]), ("ah64d", ["pilote", "cpg"]))
        self.assertEqual([e["id"] for e in profil["ecrans"]], ["mpd_gauche", "mpd_droit", "tedac"])
        self.bouton("mpd_gauche", "T1", siege="cpg")
        self.assertEqual(self.lua.recevoir(), "44 3001 1")
        self.bouton("mpd_droit", "M", siege="pilote")       # « M » est B1
        self.bouton("mpd_droit", "B1", siege="pilote")
        self.assertEqual(self.lua.recevoir(), "43 3018 1")
        # Les écrans du Hornet n'existent plus : rien ne part.
        self.assertEqual(self.bouton("ddi_gauche", "18").status_code, 404)
        self.assertEqual(self.client.get("/api/planche").status_code, 404)
        self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(self.lua.recevoir(), "84 3001 1")
        # Le dernier profil reste quand DCS se tait.
        self.lua.annoncer(self.pont.port_etat, "-")
        time.sleep(0.1)
        self.assertEqual(self.client.get("/api/profil").json()["id"], "ah64d")

    def test_appareil_sans_page_de_kneeboard_sure(self):
        self.piloter("F-16C_50")
        r = self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(r.status_code, 409)
        self.silence()
        self.piloter("Bf-109K-4")
        profil = self.client.get("/api/profil").json()
        self.assertEqual((profil["id"], profil["ecrans"]), ("generique", []))

    def test_planche_du_hornet(self):
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        envoi = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        envoi.sendto(("ind 6\n" + TestPlanche.TEXTE_UFC).encode(),
                     ("127.0.0.1", self.pont.port_etat))
        envoi.sendto(b"arg 217=0.586 13=1.0", ("127.0.0.1", self.pont.port_etat))
        envoi.close()
        for _ in range(100):
            d = self.client.get("/api/planche").json()
            if d["ufc"] and d["instruments"]:
                break
            time.sleep(0.02)
        self.assertEqual(d["ufc"]["bloc"][2], "  127.500")
        self.assertEqual(d["instruments"]["badin"]["valeur"], 200.0)
        self.assertTrue(d["voyants"]["MASTER CAUTION"])
        self.assertIsNone(d["ifei"])                      # rien reçu : rien inventé

    def test_touches_et_molettes_de_l_ufc(self):
        self.client.post("/api/ufc", json={"touche": "ENT", "enfonce": True})
        self.assertEqual(self.lua.recevoir(), "25 3029 1")
        self.client.post("/api/ufc", json={"touche": "COMM1", "sens": -1})
        self.assertEqual(self.lua.recevoir(), "25 3033 -0.2")
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "HUD"}).status_code, 404)
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "COMM2", "sens": 3}
                                          ).status_code, 422)
        self.silence()

    def test_etat_suit_les_annonces_du_script(self):
        self.assertEqual(self.client.get("/api/etat").json()["dcs"],
                         {"connecte": False, "appareil": None})
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        for _ in range(50):
            dcs = self.client.get("/api/etat").json()["dcs"]
            if dcs["connecte"]:
                break
            time.sleep(0.02)
        self.assertEqual(dcs, {"connecte": True, "appareil": "FA-18C_hornet"})
        self.lua.annoncer(self.pont.port_etat, "-")
        for _ in range(50):
            dcs = self.client.get("/api/etat").json()["dcs"]
            if dcs["appareil"] is None:
                break
            time.sleep(0.02)
        self.assertEqual(dcs, {"connecte": True, "appareil": None})

    def test_ecrans_decrits_pour_la_page(self):
        profil = self.client.get("/api/profil").json()
        self.assertEqual([e["id"] for e in profil["ecrans"]], ["ddi_gauche", "ddi_droit", "ampcd"])
        self.assertEqual(len(profil["ecrans"][0]["boutons"]), 20)
        self.assertEqual(profil["panneaux"], ["ufc", "ifei", "secours"])

    def test_kneeboard_dossier_et_mission(self):
        (self.saved / "Kneeboard" / "FA-18C_hornet").mkdir(parents=True)
        (self.saved / "Kneeboard" / "commune.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "FA-18C_hornet" / "hornet.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "notes.txt").write_text("pas une page")
        (self.saved / "Missions").mkdir()
        with zipfile.ZipFile(self.saved / "Missions" / "Vol test.miz", "w") as z:
            z.writestr("mission", "x")
            z.writestr("KNEEBOARD/IMAGES/briefing.png", PNG)
        with zipfile.ZipFile(self.saved / "Missions" / "Sans pages.miz", "w") as z:
            z.writestr("mission", "x")

        carnets = self.client.get("/api/kneeboard").json()
        self.assertEqual([(c["id"], c["pages"]) for c in carnets],
                         [("avion", 2), ("miz:Vol test.miz", 1)])
        for c in carnets:
            r = self.client.get(c["url"] + "/0")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["content-type"], "image/png")
            self.assertEqual(r.content, PNG)
        self.assertEqual(self.client.get(carnets[0]["url"] + "/2").status_code, 404)
        self.assertEqual(self.client.get("/api/kneeboard/inconnu/0").status_code, 404)

    def test_mission_en_cours_retrouvee_dans_le_journal_de_dcs(self):
        """Vu en vrai : une mission jouée depuis une copie temporaire, hors du
        dossier Missions ; seul dcs.log dit laquelle."""
        temporaire = self.saved / "Temp" / "tempMission.miz"
        temporaire.parent.mkdir()
        with zipfile.ZipFile(temporaire, "w") as z:
            z.writestr("mission", "x")
            z.writestr("KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", PNG)
        (self.saved / "Logs").mkdir()
        (self.saved / "Logs" / "dcs.log").write_text(
            "2026-10-25 16:28:22.965 INFO    Dispatcher (Main): loadMission "
            f"{temporaire}\r\n"
            "2026-10-25 16:28:37.552 INFO    Dispatcher (Main): loadMission Done: "
            "Control passed to the player\r\n", encoding="utf-8")
        carnets = self.client.get("/api/kneeboard").json()
        self.assertEqual((carnets[0]["id"], carnets[0]["titre"], carnets[0]["pages"]),
                         ("avion", "Kneeboard de l'avion", 1))
        self.assertEqual(self.client.get(carnets[0]["url"] + "/0").content, PNG)

    def test_kneeboard_de_l_avion_en_multijoueur(self):
        """Vu dans dcs.log : en multijoueur, DCS charge la mission du serveur
        depuis l'enregistrement de la partie (.trk). Kneeboard de l'avion :
        mission, puis module, puis pages perso ; cartes à part."""
        import io

        from PIL import Image

        from tablette.kneeboard import lister_carnets
        trk = self.saved / "Tracks" / "Multiplayer" / "Op-20261026-211500.trk"
        trk.parent.mkdir(parents=True)
        with zipfile.ZipFile(trk, "w") as z:
            z.writestr("mission", 'mission = {\n\t["theatre"] = "Caucasus",\n}\n')
            z.writestr("KNEEBOARD/IMAGES/freq.png", PNG)
            z.writestr("KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", PNG)
            z.writestr("KNEEBOARD/F-16C_50/IMAGES/viper.png", PNG)       # pas pour nous
        (self.saved / "Logs").mkdir()
        (self.saved / "Logs" / "dcs.log").write_text(
            f"2026-10-26 21:15:00.000 INFO    Dispatcher (Main): loadMission {trk}\r\n",
            encoding="utf-8")
        (self.saved / "Kneeboard" / "FA-18C_hornet").mkdir(parents=True)
        (self.saved / "Kneeboard" / "FA-18C_hornet" / "perso.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "commune.png").write_bytes(PNG)

        # Un dossier DCS : le module (dossier « FA-18C », appareil
        # « FA-18C_hornet ») et la carte (planches, dont une en BMP).
        dcs = self.saved / "DCSWorld"
        module = dcs / "Mods" / "aircraft" / "FA-18C"
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages").mkdir(parents=True)
        (module / "entry.lua").write_text(
            "make_flyable('FA-18C_hornet', current_mod_path..'/Cockpit/Scripts/', nil)")
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages" / "1.png").write_bytes(PNG)
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages" / "1.lua").write_text("--")
        terrain = dcs / "Mods" / "terrains" / "Caucasus"
        (terrain / "Kneeboard").mkdir(parents=True)
        (terrain / "entry.lua").write_text('local self_ID = "Caucasus";\n')   # tel quel
        (terrain / "Kneeboard" / "00_map.png").write_bytes(PNG)
        tampon = io.BytesIO()
        Image.new("RGB", (4, 6), "white").save(tampon, "BMP")
        (terrain / "Kneeboard" / "01_kobuleti.bmp").write_bytes(tampon.getvalue())

        carnets = lister_carnets(self.saved, "FA-18C_hornet", dcs)
        noms = {c.id: [p.name if isinstance(p, Path) else p[1] for p in c.pages] for c in carnets}
        self.assertEqual(noms["avion"], [
            "KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", "KNEEBOARD/IMAGES/freq.png",
            "1.png", "perso.png", "commune.png"])
        self.assertEqual(noms["carte:Caucasus"], ["00_map.png", "01_kobuleti.bmp"])
        self.assertEqual([c.titre for c in carnets][:2], ["Kneeboard de l'avion", "Cartes : Caucasus"])

        # Par l'API, DCS une fois connu : la planche BMP arrive en PNG.
        self.dossier_dcs = dcs
        r = self.client.get("/api/kneeboard/carte%3ACaucasus/1")
        self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/png"))
        self.assertEqual(Image.open(io.BytesIO(r.content)).size, (4, 6))
        self.dossier_dcs = None             # DCS fermé : le dernier dossier connu sert
        self.assertEqual(self.client.get("/api/kneeboard").json()[1]["id"], "carte:Caucasus")

    def test_kneeboard_de_dcs_sur_pc_ou_tablette(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config

        class FausseVideo:
            def kneeboard_ouvert(self):
                return True

        client = TestClient(create_app(Config(saved_games=self.saved), self.pont,
                                       FausseVideo(), dossier_dcs=lambda: None))
        self.assertEqual(client.get("/api/etat").json()["kneeboard"],
                         {"sur": "pc", "ouvert": None})
        # DCS muet : la tablette prend le kneeboard, sans savoir s'il est ouvert.
        self.assertEqual(client.get("/api/etat?kneeboard=tablette").json()["kneeboard"],
                         {"sur": "tablette", "ouvert": None})
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        for _ in range(100):
            if client.get("/api/etat").json()["dcs"]["connecte"]:
                break
            time.sleep(0.02)
        self.assertEqual(client.get("/api/etat?kneeboard=tablette").json()["kneeboard"],
                         {"sur": "tablette", "ouvert": True})
        self.assertEqual(client.get("/api/etat?kneeboard=pc").json()["kneeboard"],
                         {"sur": "pc", "ouvert": None})

    def test_kneeboard_de_dcs_affiche_depuis_la_tablette(self):
        """Le coup d'œil (K) : +1 l'affiche, -1 le cache ; rien d'autre."""
        self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": True})
        self.assertEqual(self.lua.recevoir(), "kneeboard 1")
        self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": False})
        self.assertEqual(self.lua.recevoir(), "kneeboard -1")
        for valeur in (1, "true", None):
            r = self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": valeur})
            self.assertEqual(r.status_code, 422, valeur)
        self.silence()

    def test_version_dans_l_etat(self):
        """La page se recharge quand le serveur change de version."""
        from tablette import VERSION
        self.assertEqual(self.client.get("/api/etat").json()["version"], VERSION)

    def test_pages_du_kneeboard_de_dcs(self):
        self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(self.lua.recevoir(), "68 3001 1")
        self.client.post("/api/kneeboard/dcs/page", json={"sens": -1})
        self.assertEqual(self.lua.recevoir(), "68 3002 1")
        for sens in (0, 2, "1", None):
            r = self.client.post("/api/kneeboard/dcs/page", json={"sens": sens})
            self.assertEqual(r.status_code, 422, sens)

    def test_image_servie_ou_raison_donnee(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        from tablette.video import PasDImage

        class FausseVideo:
            def image(self, viewport):
                if viewport == "CENTER_MFCD":
                    raise PasDImage("CENTER_MFCD non exporté")
                return b"\xff\xd8\xff" + viewport.encode()

        client = TestClient(create_app(Config(saved_games=self.saved), self.pont,
                                       FausseVideo()))
        r = client.get("/api/video/ddi_droit")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/jpeg")
        self.assertEqual(r.content, b"\xff\xd8\xffRIGHT_MFCD")
        r = client.get("/api/video/ampcd")
        self.assertEqual((r.status_code, r.json()["detail"]), (503, "CENTER_MFCD non exporté"))
        self.assertEqual(client.get("/api/video/kneeboard").content, b"\xff\xd8\xffKNEEBOARD")
        self.assertEqual(client.get("/api/video/hud").status_code, 404)

    def test_page_servie(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("DCS Tablette", r.text)


if __name__ == "__main__":
    unittest.main()
