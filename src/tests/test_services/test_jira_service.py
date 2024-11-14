from python_apis.services.jira_service import JiraService


def main():
    ad_ou = JiraService()
    ad_ou.create_table()
    ad_ou.update_issues_db()

if __name__ == '__main__':
    main()
