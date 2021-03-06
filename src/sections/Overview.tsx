import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Typography, Card, CardHeader, CardContent, Grid, FormGroup, Switch, FormControlLabel } from '@mui/material';
import { AbstractSection, SectionProps } from '../common';


interface OverviewDataRow {
    ticker: string;
    currency: string;
    last_price: number;
    volume: number;
    value: number;
    fee: number;
    invested: number;
    profit: number;
    manual_value_correction: number;
    type: string;
    average_price: number;
}

interface DividendsDataRow {
    ticker: string;
    currency: string;
    dividends: number;
}

type OverviewResponse = Array<OverviewDataRow>;
type DividendsResponse = {[ticker:string]:DividendsDataRow};
type DividendsSumResponse = {[ticker:string]:DividendsDataRow};

interface OverviewState {
    investment: number;
    fees: number;
    value: number;
    profit: number;
    savingsDeposit: number;
    savingsValue: number;
    overview: Array<OverviewDataRow>;
    dividends: DividendsResponse;
    dividendsSum: DividendsSumResponse;
    types: Array<string>;
    groupByType: boolean;
}

interface OverviewProps {}

export class Overview extends AbstractSection<OverviewProps, OverviewState> {

    sectionName = () => 'Overview';

    constructor(props: OverviewProps & SectionProps) {
        super(props);
        this.state = {
            investment: 0,
            fees: 0,
            value: 0,
            profit: 0,
            savingsDeposit: 0,
            savingsValue: 0,
            overview: [],
            dividends: {},
            dividendsSum: {},
            types: [],
            groupByType: false,
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadOverview().then(() =>
            this.loadDividends().then(() =>
                this.loadDividendsSum().then(() =>
                    this.props.displayProgressBar(false)
                )
            )
        );
    }

    loadOverview() {
        return fetch('/overview/get')
            .then<OverviewResponse>(res => res.json())
            .then(overview => {
                const types: Array<string> = [];
                overview.forEach(v => {
                    if (!types.includes(v.type)) types.push(v.type);
                });
                types.sort();
                this.setState({
                    overview,
                    types,
                    investment: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.invested, 0),
                    fees: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.fee, 0),
                    value: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.value, 0),
                    profit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.profit, 0),
                    savingsDeposit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.invested : prev, 0),
                    savingsValue: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.value : prev, 0),
                });
            });
    }

    loadDividends() {
        return fetch('/dividends/calc')
            .then<DividendsResponse>(res => res.json())
            .then(dividends => {
                this.setState({dividends});
            });
    }

    loadDividendsSum() {
        return fetch('/dividends/sum')
            .then<DividendsSumResponse>(res => res.json())
            .then(dividendsSum => {
                this.setState({dividendsSum});
            });
    }

    render() {
        return (
            <Box>
                <Grid container spacing={2}>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Investment'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.investment)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Fees'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.fees)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.value)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Profit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.profit)} ({this.formatPercents(this.state.profit/this.state.investment)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Deposit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsDeposit)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsValue)} ({this.formatPercents((this.state.savingsValue-this.state.savingsDeposit)/this.state.savingsValue)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                <FormGroup>
                    <FormControlLabel control={<Switch checked={this.state.groupByType} onChange={(e, value) => this.setState({groupByType: value})}/>} label="Group by type" />
                </FormGroup>

                {this.state.groupByType ?
                    this.state.types.map(type =>
                        <Card elevation={3} sx={{marginBottom: '1em'}}>
                            <CardHeader title={type} />
                            <CardContent>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Ticker</TableCell>
                                                <TableCell align='right'>Last price</TableCell>
                                                <TableCell align='right'>Avg price</TableCell>
                                                <TableCell align='center'>Volume</TableCell>
                                                <TableCell align='right'>Invested</TableCell>
                                                <TableCell align='right'>Fee</TableCell>
                                                <TableCell align='right'>Value</TableCell>
                                                <TableCell colSpan={2} align='center'>Profit</TableCell>
                                                <TableCell colSpan={2} align='center'>Dividends</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {this.state.overview.filter(item => item.type === type).map((item, i) =>
                                                <TableRow key={i} sx={{backgroundColor: item.profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                    <TableCell>{item.ticker}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.last_price, item.currency)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.average_price, item.currency)}</TableCell>
                                                    <TableCell align='center'>{item.volume ? item.volume : null}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.invested)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.fee)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.profit)}</TableCell>
                                                    <TableCell align='right'>{this.formatPercents(item.profit/item.invested)}</TableCell>
                                                    <TableCell align='right'>{this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, this.state.dividends[item.ticker].currency) : null}</TableCell>
                                                    <TableCell align='right'>{this.state.dividendsSum[item.ticker] ? this.formatCurrency(this.state.dividendsSum[item.ticker].dividends, this.state.dividendsSum[item.ticker].currency) : null}</TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </CardContent>
                        </Card>
                    ) :
                    <Card elevation={3}>
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Ticker</TableCell>
                                            <TableCell align='right'>Last price</TableCell>
                                            <TableCell align='right'>Avg price</TableCell>
                                            <TableCell align='center'>Volume</TableCell>
                                            <TableCell align='right'>Invested</TableCell>
                                            <TableCell align='right'>Fee</TableCell>
                                            <TableCell align='right'>Value</TableCell>
                                            <TableCell colSpan={2} align='center'>Profit</TableCell>
                                            <TableCell colSpan={2} align='center'>Dividends</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {this.state.overview.map((item, i) =>
                                            <TableRow key={i} sx={{backgroundColor: item.profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                <TableCell>{item.ticker}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.last_price, item.currency)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.average_price, item.currency)}</TableCell>
                                                <TableCell align='center'>{item.volume ? item.volume : null}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.invested)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.fee)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.profit)}</TableCell>
                                                <TableCell align='right'>{this.formatPercents(item.profit/item.invested)}</TableCell>
                                                <TableCell align='right'>{this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, this.state.dividends[item.ticker].currency) : null}</TableCell>
                                                <TableCell align='right'>{this.state.dividendsSum[item.ticker] ? this.formatCurrency(this.state.dividendsSum[item.ticker].dividends, this.state.dividendsSum[item.ticker].currency) : null}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                }
            </Box>
        )
    }
}